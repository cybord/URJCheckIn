# Create your views here.
from django.http import (HttpResponse, HttpResponseBadRequest,
                        HttpResponseRedirect)
from django.template import loader, RequestContext
from django.shortcuts import render_to_response
from django.utils.datastructures import MultiValueDictKeyError
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import logout
from django.contrib.auth.forms import PasswordChangeForm
from django.views.decorators.debug import sensitive_post_parameters
from models import (UserProfile, Lesson, Subject, CheckIn, LessonComment,
                    ForumComment, remove_if_exists, AdminTask, get_free_room)
from django.utils import timezone
from forms import (ProfileEditionForm, CheckInForm, SubjectForm,
                    ExtraLessonForm, ProfileImageForm, ControlFilterForm,
                    CodesFilterForm, ReportForm, ChangeEmailForm, FreeRoomForm)
import datetime
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import json
from django.db import IntegrityError
import pytz

WEEK_DAYS_BUT_SUNDAY = ['Lunes', 'Martes', 'Mi&eacute;rcoles', 'Jueves',
                        'Viernes', 'S&aacute;bado']

def ajax_required(funct):
    """Decorator requiring an ajax request"""
    def wrap(request, *args, **kwargs):
        if not request.is_ajax():
            return HttpResponseBadRequest()
        return funct(request, *args, **kwargs)
    wrap.__doc__ = funct.__doc__
    wrap.__name__ = funct.__name__
    return wrap


def my_paginator(request, collection, n_elem):
    """
    Pagina la coleccion de objetos collection con n_elem objetos por
    pagina. El numero de pagina lo obtiene de el parametro 'page'
    de la querystring de request
    """
    paginator = Paginator(collection, n_elem)
    page = request.GET.get('page')
    try:
        results = paginator.page(page)
    except PageNotAnInteger:
        #Si no es un entero devuelve la primera
        results = paginator.page(1)
    except EmptyPage:
        #Si no hay tantas paginas devuelve la ultima
        results = paginator.page(paginator.num_pages)
    return results


def response_ajax_or_not(request, ctx):
    """
    Devuelve un HttpResponse con un objeto JSON con '#mainbody' el
    contenido de ctx['htmlname'] y 'url' la url pedida si la peticion es
    ajax o la pagina main.html renderizada con el contexto ctx si no es
    ajax
    """
    if request.is_ajax():
        html = loader.get_template(ctx['htmlname']).render(
                                   RequestContext(request, ctx))
        resp = {'#mainbody':html, 'url': request.get_full_path()}
        return HttpResponse(json.dumps(resp), content_type="application/json")
    return render_to_response('main.html', ctx,
                              context_instance=RequestContext(request))


def not_found(request):
    """
    Devuelve una pagina que indica que la pagina solicitada no existe
    """
    return response_ajax_or_not(request, {'htmlname': '404.html'})


def send_error_page(request, error):
    """Devuelve una pagina de error"""
    return response_ajax_or_not(request, {'htmlname': 'error.html',
                                          'message': error})


@login_required
def help_page(request):
    """Devuelve una pagina de ayuda"""
    return response_ajax_or_not(request, {'htmlname': 'help.html'})


@login_required
def home(request):
    """Devuelve la pagina de inicio"""
    if request.method != "GET":
        return method_not_allowed(request)

    if request.user.is_staff:
        tasks = AdminTask.objects.filter(done=False).order_by('time')[0:15]
    else:
        tasks = None

    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        return response_ajax_or_not(request, {'tasks': tasks,
                                              'htmlname': 'home.html'})

    try:
        week = int(request.GET.get('page'))
    except (TypeError, ValueError):
        week = 0
    today = datetime.date.today()
    monday = today + datetime.timedelta(days= -today.weekday() + 7*week)
    ctx = {'events': get_week_lessons(monday, profile.subjects.all()),
           'firstday':monday, 'lastday':monday + datetime.timedelta(days=6),
           'previous':week-1, 'next': week+1, 'tasks': tasks,
           'htmlname': 'home.html'}
    return response_ajax_or_not(request, ctx)


def get_week_lessons(monday, subjects):
    """
    Devuelve las clases de las asignaturas 'subjects' desde el lunes
    'monday' hasta el sabado de esa misma semana
    El formato devuelto es un array de longitud 6 y en cada posicion un
    diccionario con clave 'day' igual al string del dia de la semana y
    'events' con las clases de ese dia
    """
    events = []
    all_lessons = Lesson.objects.filter(subject__in=subjects)
    current_tz = str(timezone.get_current_timezone())
    for day in WEEK_DAYS_BUT_SUNDAY:
        date = monday + datetime.timedelta(
                                    days=WEEK_DAYS_BUT_SUNDAY.index(day))
        init_date = pytz.timezone(current_tz).localize(datetime.datetime(
                            date.year, date.month, date.day), is_dst=None)
        end_date = init_date + datetime.timedelta(days=1)
        events.append({
                        'day': day,
                        'events': all_lessons.filter(
                                start_time__gte = init_date,
                                start_time__lt = end_date 
                            ).order_by('start_time')
                    })
    return events


def save_checkin(form, profile, lesson):
    """
    Guarda el CheckIn del usuario con perfil profile en la clase lesson
    con la informacion del formulario form. En caso de ser un profesor
    actualizara ademas los alumnos que ha contado este en la clase
    Devuelve un diccionario que cumple la descripcion de retorno del
    metodo process_checkin
    """
    checkin = CheckIn(user=profile.user, lesson=lesson)
    cform = CheckInForm(form, instance=checkin)
    if cform.is_valid():
        try:
            cform.save()
        except IntegrityError:
            return {'ok': False, 'form': CheckInForm(),
                    'msg': 'Ya has realizado el checkin de esta clase'}
        if not profile.is_student:
            try:
                n_stud = form.__getitem__("n_students")
                lesson.students_counted = int(n_stud)
                lesson.save()
            except (ValueError, MultiValueDictKeyError):
                pass
        return {'ok': True, 'form': CheckInForm(),
                'msg': 'Checkin realizado con &eacute;xito'}
    else:
        return {'ok': False, 'form': cform}


def process_checkin(request):
    """
    Procesa un formulario para hacer checkin y devuelve un diccionario
    con 'ok' = True si se realiza con exito o 'ok': False en caso
    contrario. Devuelve a veces un 'msg' informativo de lo ocurrido y
    devuelve siempre 'form' = al checkinform
    """
    form = request.POST
    try:
        idsubj = form.__getitem__("subject")
    except (ValueError, MultiValueDictKeyError):
        return {'msg': 'Informacion de la asignatura incorrecta.',
                'form': CheckInForm(form)}
    try:
        profile = UserProfile.objects.get(user=request.user)
        subject = profile.subjects.get(id=idsubj)
        lesson = subject.lesson_set.get(start_time__lte=timezone.now(),
                                        end_time__gte=timezone.now())
    except UserProfile.DoesNotExist:
        return {'msg': 'No tienes un perfil creado.', 
                'form': CheckInForm(form), 'ok': False}
    except Subject.DoesNotExist:
        return {'msg': 'No estas matriculado en esa asignatura.',
                'form': CheckInForm(form), 'ok': False}
    except Lesson.DoesNotExist:
        return {'msg': 'Ahora no hay ninguna clase de la asignatura '
                + str(subject), 'form': CheckInForm(form), 'ok': False}
    except Lesson.MultipleObjectsReturned:
        return {'msg': 'Actualmente hay dos clases de ' + str(subject) + 
                ', por favor, contacte con un administrador',
                'form': CheckInForm(form), 'ok': False}
    return save_checkin(form, profile, lesson)


@login_required
def checkin_page(request):
    """
    Devuelve la pagina para hacer check in y procesa un checkin si
    recibe un POST
    """
    if request.method == "POST":
        resp = process_checkin(request)
        if request.is_ajax():
            if not 'msg' in resp:
                if not resp['ok']:
                    resp['errors'] = resp['form'].errors
            del resp['form']
            return HttpResponse(json.dumps(resp),
                                content_type="application/json")
    elif request.method != "GET":
        return method_not_allowed(request)

    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        return send_error_page(request, 'No tienes un perfil creado.')
    
    subjects = profile.subjects.all()
    ctx = {'htmlname': 'checkin.html', 'form': CheckInForm(),
            'profile': profile, 'subjects': subjects}
    if request.method == "POST":
        ctx['form'] = resp['form']
        if 'msg' in resp:
            ctx['msg'] = resp['msg']
        if 'ok' in resp:
            ctx['ok'] = resp['ok']

    return response_ajax_or_not(request, ctx)


@login_required
def profile_page(request, iduser):
    """
    Devuelve la pagina de perfil del usuario loggeado y modifica el
    perfil si recibe un POST
    """
    if request.method != "GET" and request.method != "POST":
        return method_not_allowed(request)

    try:
        profile = UserProfile.objects.get(user=iduser)
    except UserProfile.DoesNotExist:
        #mostrara el formulario para cambiar la password y el email
        if str(request.user.id) == iduser:
            resp = response_ajax_or_not(request, {
                    'htmlname': 'profile.html', 
                    'email_form': ChangeEmailForm(instance=request.user)})
        else:
            resp = send_error_page(request, 'El usuario con id ' + iduser + 
                               ' no tiene perfil')
        return resp

    if request.method == "POST":
        if iduser != str(request.user.id):
            return send_error_page(request, 'Est&aacute;s intentando cambiar' +
                                   ' un perfil distinto del tuyo')
        pform = ProfileEditionForm(request.POST, instance=profile)
        if not pform.is_valid():
            if request.is_ajax():
                return HttpResponse(json.dumps({'errors': pform.errors}), 
                                    content_type="application/json")
            #si no lo obtengo de nuevo cuando renderice con
            # profile puede aparecer mal la edad
            profile = UserProfile.objects.get(user=iduser)
        else:
            pform.save()
            if request.is_ajax():
                resp = {'user': {'age': profile.age,
                                 'description': profile.description, 
                                 'email': profile.user.email, 
                                 'show_email': profile.show_email}}
                return HttpResponse(json.dumps(resp),
                                    content_type="application/json")    
    else: # si es un POST coge el form que ha recibido
        pform = ProfileEditionForm(instance=profile)
    ctx = {'profile': profile, 'form': pform, 'htmlname': 'profile.html',
           'form_img': ProfileImageForm(),
           'email_form': ChangeEmailForm(instance=request.user)}
    return response_ajax_or_not(request, ctx)


@sensitive_post_parameters()
@login_required
@ajax_required
def password_change(request):
    """Metodo de django.contrib.auth adaptado a ajax"""
    if request.method == "POST":
        pform = PasswordChangeForm(user=request.user, data=request.POST)
        if pform.is_valid():
            pform.save()
            return HttpResponse(json.dumps({'ok': True}),
                                content_type="application/json")
        else:
            return HttpResponse(json.dumps({'errors': pform.errors}),
                                content_type="application/json")
    else:
        return method_not_allowed(request)


@login_required
def my_logout(request):
    """Cierra sesion"""
    resp = logout(request)
    if request.is_ajax():
        if resp.status_code == 200:
            html = loader.get_template('registration/login_body.html').render(
                                                RequestContext(request, {}))
            ajax_resp = {'body': html, 'url': '/login'}
            return HttpResponse(json.dumps(ajax_resp),
                                content_type="application/json")
    return resp


@login_required
def change_profile_img(request, action):
    """Modifica la foto de perfil de request.user"""
    if request.method != "POST":
        return method_not_allowed(request)

    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:            
        return send_error_page(request, 'No tienes perfil de usuario')
    img_url = '/img/default_profile_img.png'
    if action == 'edit':
        pform = ProfileImageForm(request.POST, request.FILES, instance=profile)
        if pform.is_valid():
            pform.save()
            img_url = profile.photo.url
    else: #delete
        remove_if_exists('profile_photos/' + str(request.user.id))
        profile.photo = None
        profile.save()
    if request.is_ajax():
        return HttpResponse(json.dumps({'ok': True, 'img_url': img_url}), 
                            content_type="application/json")
    return HttpResponseRedirect('/profile/view/' + str(request.user.id))


@login_required
def process_lesson(request, idlesson):
    """
    Procesa las peticiones sobre una clase y guarda un LessonComment si
    recibe un POST
    """
    if request.method != "GET" and request.method != "POST":
        return method_not_allowed(request)

    try:
        lesson = Lesson.objects.get(id=idlesson)
        profile = lesson.subject.userprofile_set.get(user=request.user)
    except Lesson.DoesNotExist:
        return send_error_page(request,
                               'La clase a la que intentas acceder no existe.')
    except UserProfile.DoesNotExist:
        #Si tiene el permiso puede ver las clases
        if request.user.has_perm('app.can_see_statistics'):
            profile = None
        else:
            return send_error_page(request, 'No est&aacutes matriculado en ' + 
                                   str(lesson.subject))

    if request.method == "POST" and profile:
        if profile.is_student:
            return send_error_page(request,'Solo los profesores pueden ' +
                                   'comentar en las clases')
        resp = save_lesson_comment(request, lesson)
        if request.is_ajax():
            return HttpResponse(json.dumps(resp),
                                content_type="application/json")
    
    lesson_state = lesson_str_state(lesson, request.user)
    comments = my_paginator(request,
                            lesson.lessoncomment_set.all().order_by('-date'),
                            10)
    profesors = lesson.subject.userprofile_set.filter(is_student=False)
    ctx = {'lesson':lesson, 'comments':comments, 'profile':profile,
           'lesson_state':lesson_state, 'profesors':profesors,
           'subject': lesson.subject, 'htmlname': 'lesson.html'}
    if lesson_state != "sin realizar":
        show_opinions = True if (not profile) else (not profile.is_student)
        if show_opinions: 
            opinions = lesson.checkin_set.filter(\
                                    user__userprofile__is_student=True)
            ctx['opinions'] = opinions
    return response_ajax_or_not(request, ctx)


@login_required
def lesson_attendance(request, idlesson):
    """
    Procesa las peticiones sobre una clase y guarda un LessonComment si
    recibe un POST
    """
    if request.method != "GET":
        return method_not_allowed(request)

    try:
        lesson = Lesson.objects.get(id=idlesson)
        lesson.subject.userprofile_set.get(user=request.user, is_student=False)
    except Lesson.DoesNotExist:
        return send_error_page(request, 'La clase a la que intentas acceder ' +
                               'no existe.')
    except UserProfile.DoesNotExist:
        if not request.user.has_perm('app.can_see_statistics'):
            return send_error_page(request, 'Solo los profesores de la ' +
                                   'asignatura tienen acceso.')
    
    ctx = {'lesson':lesson,
            'checkins': lesson.checkin_set.all().order_by(\
                                            'user__userprofile__is_student'),
            'htmlname': 'lesson_attendance.html'}
    return response_ajax_or_not(request, ctx)


@login_required
def save_lesson_comment(request, lesson):
    """
    Guarda un LessonComment con la informacion del formulario recibido
    para la clase lesson y el usuario request.user y devuelve un
    diccionario con un ok = True si la peticion no es ajax o la
    respuesta para una peticion ajax. O con error = mensaje de error si
    se produce un error
    """
    try:
        comment = request.POST.__getitem__("comment")
    except MultiValueDictKeyError:
        return {'error': 'Formulario para comentar incorrecto'}
    comment = comment[:250]
    new_comment = LessonComment(comment=comment, user=request.user,
                                lesson=lesson)
    new_comment.save()
    if request.is_ajax():
        html = loader.get_template('pieces/comments.html').render(\
                        RequestContext(request, {'comments': [new_comment]}))
        return {'ok': True, 'comment': html, 'idcomment': new_comment.id,
                'idlesson':lesson.id}
    else:
        return {'ok': True}
    

def lesson_str_state(lesson, user):
    """
    Devuelve un string indicando el estado de la clase o si asististe o
    no si ya se ha realizado la clase
    """
    if lesson.start_time > timezone.now():
        return 'sin realizar'
    elif lesson.end_time < timezone.now():
        try:
            lesson.checkin_set.get(user=user)
            return 'asististe'
        except CheckIn.DoesNotExist:
            return 'no asististe'
    else:
        return 'imperti&eacute;ndose en este momento'


def method_not_allowed(request):
    """Devuelve una pagina indicando que el metodo no esta permitido"""
    if request.is_ajax():
        resp = {'error': 'Metodo ' + request.method + ' no soportado'}
        return HttpResponse(json.dumps(resp), content_type="application/json")
    return render_to_response('error.html',
                              {'message': "M&eacutetodo " + request.method +
                               " no soportado en " + request.path},
                              context_instance=RequestContext(request))


@login_required
def forum(request):
    """Devuelve la pagina del foro y almacena comentarios nuevos"""
    if request.method == "POST":
        resp = save_forum_comment(request)
        if request.is_ajax():
            return HttpResponse(json.dumps(resp),
                                content_type="application/json")
    elif request.method != "GET":
        return method_not_allowed(request)

    comments =  ForumComment.objects.all().order_by('-date')
    ctx = {'comments': my_paginator(request, comments, 10),
           'htmlname': 'forum.html'}
    return response_ajax_or_not(request, ctx)


@login_required
def save_forum_comment(request):
    """
    Guarda un ForumComment del usuario request.user con la informacion
    del formulario recibido y devuelve un diccionario con un ok = True
    si la peticion no es ajax o la respuesta para una peticion ajax. O
    con error = mensaje de error si se produce un error"""
    try:
        comment = request.POST.__getitem__("comment")
    except MultiValueDictKeyError:
        return {'error': 'Formulario para comentar incorrecto'}
    #si el comentario tiene mas de 150 caracteres se corta
    comment = comment[:150]
    new_comment = ForumComment(comment=comment, user=request.user)
    new_comment.save()
    if request.is_ajax():
        html = loader.get_template('pieces/comments.html').render(\
                        RequestContext(request, {'comments': [new_comment]}))
        return {'ok': True, 'comment': html, 'idcomment': new_comment.id}
    else:
        return {'ok': True}


@login_required
def subjects_page(request):
    """Devuelve la pagina con las asignaturas del usuario registrado"""
    if request.method != 'GET':
        return method_not_allowed(request)

    try:
        profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:            
        return send_error_page(request, 'No tienes un perfil creado.')
    subjects = profile.subjects.all()
    comments = LessonComment.objects.filter(
                                        lesson__subject__in = subjects
                                    ).order_by('-date')[0:15]
    ctx = {'subjects': subjects.filter(is_seminar=False),
           'seminars': subjects.filter(is_seminar=True),
           'comments': comments,
           'htmlname': 'subjects.html'}
    return response_ajax_or_not(request, ctx)
    

@login_required
def seminars(request):
    """Devuelve la pagina con las asignaturas del usuario registrado"""
    if request.method != "GET" and request.method != "POST":
        return method_not_allowed(request)

    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:            
        return send_error_page(request, 'No tienes un perfil creado.')

    if request.method == "POST":
        if profile.is_student:
            return send_error_page(request, 'Los estudiantes no pueden crear' +
                                   'seminarios')

        subj = Subject(is_seminar=True, creator=request.user)
        csform = SubjectForm(request.POST, instance=subj)
        if not csform.is_valid():
            if request.is_ajax():
                return HttpResponse(json.dumps({'errors': csform.errors}), 
                                    content_type="application/json")
        else:
            new_subj = csform.save()
            profile.subjects.add(new_subj)
            if request.is_ajax():
                resp = HttpResponse(json.dumps({'idsubj': new_subj.id}),
                                    content_type="application/json")
            else:
                resp = HttpResponseRedirect('/subjects/' + str(new_subj.id))
            return resp

    future_seminars = Subject.objects.filter(
                        is_seminar=True        
                    ).filter(
                        first_date__gt = timezone.now()
                    ).filter(
                        degrees__in = profile.degrees.all()
                    ).distinct().order_by('first_date')
    if request.method != "POST":
        csform = SubjectForm()
    ctx = {'profile':profile, 'seminars': future_seminars, 'form': csform, 
           'htmlname': 'seminars.html'}
    return response_ajax_or_not(request, ctx)

@login_required
def subject_page(request, idsubj):
    """
    Devuelve la pagina con la informacion y las clases de una asignatura
    mediante un POST permite al usuario apuntarse o desapuntarse de un
    seminario
    """
    if request.method != 'GET' and request.method != 'POST':
        return method_not_allowed(request)

    try:
        subject = Subject.objects.get(id=idsubj)
        profile = UserProfile.objects.get(user=request.user)
    except Subject.DoesNotExist:
        return send_error_page(request, '#404 La asignatura a la que ' +
                               'intentas acceder no existe.')
    except UserProfile.DoesNotExist:
        #Si controla las estadisticas tiene acceso
        if request.user.has_perm('app.can_see_statistics'):
            profile = None
        else:
            return send_error_page(request, 'No tienes un perfil creado.')

    error = False
    if request.method == 'POST':
        resp = sign_in_seminar(request, subject, profile)
        if request.is_ajax():
            return HttpResponse(json.dumps(resp),
                                content_type="application/json")
        elif 'error' in resp:
            error = resp['error']

    signed = False
    if profile:
        if subject in profile.subjects.all():
            signed = True
        elif not subject.is_seminar:
            return send_error_page(request, 'No est&aacutes matriculado en ' +
                                   str(subject))
        
    lessons = subject.lesson_set.all()
    now = timezone.now()
    today = datetime.date(now.year, now.month, now.day)
    started = subject.first_date < today#Si ha empezado True
    lessons_f = my_paginator(request, 
        lessons.filter(start_time__gte=timezone.now()).order_by('end_time'),
        10)
    lessons_p = my_paginator(request,
        lessons.filter(end_time__lte=timezone.now()).order_by('-start_time'),
        10)
    ctx = {'lessons_f': lessons_f, 'lessons_p': lessons_p,
           'lessons_n': lessons.filter(end_time__gt=timezone.now(), 
                                       start_time__lt=timezone.now()),
           'profesors': subject.userprofile_set.filter(is_student=False),
           'subject': subject, 'profile':profile, 'error': error,
           'signed': signed, 'started': started,
           'timetables': subject.timetable_set.all(),
           'htmlname': 'subject.html'}
    return response_ajax_or_not(request, ctx)


@login_required
def sign_in_seminar(request, subject, profile):
    """
    Te apunta a un seminario (si no estas apuntado) o te desapunta en
    caso contrario.
    Devuelve un diccionario con error = error si ocurre un error o un ok
    = True si la peticion no es ajax o el diccionario para crear el
    objeto json para responder si la peticion es ajax
    """
    if not subject.is_seminar:
        return {'error': 'La acci&oacute;n que intentas realizar solo se ' +
                'puede realizar sobre seminarios.'}
    now = timezone.now()
    today = datetime.date(now.year, now.month, now.day)
    if subject.first_date < today:
        return {'error': 'No puedes modificar tu registro en un seminario ' +
                'que ya ha empezado'}
    else:
        if subject in profile.subjects.all():
            profile.subjects.remove(subject)
            signed = False
        else:
            if profile.is_student:
                if subject.max_students <= subject.n_students():
                    return {'error': 'No hay plazas disponibles'}
            profile.subjects.add(subject)
            signed = True
        if request.is_ajax():
            return {'signed': signed, 'is_student':profile.is_student,
                    'ok': True, 'iduser': request.user.id, 
                    'name': request.user.first_name + " " + 
                    request.user.last_name}
        else:
            return {'ok': True}


@login_required
def subject_statistics(request, idsubj):
    """
    Devuelve una pagina con las estadisticas de la asignatuda con id
    idsubj
    """
    try:
        subject = Subject.objects.get(id=idsubj)
        profile = subject.userprofile_set.get(user=request.user)
    except Subject.DoesNotExist:
        return send_error_page(request, '#404 La asignatura a la que ' +
                               'intentas acceder no existe.')
    except UserProfile.DoesNotExist:
        #Si controla las estadisticas tiene acceso
        if not request.user.has_perm('app.can_see_statistics'):
            return send_error_page(request, 'No tienes acceso a esta ' +
                                   'informaci&oacute;n.')
    ctx = {'subject': subject, 'htmlname': 'subject_statistics.html',
           'lessons_done': subject.lesson_set.filter(
                                done=True).order_by('start_time'),
           'n_lessons_past': subject.lesson_set.filter(
                                end_time__lte=timezone.now()).count()
          }
    return response_ajax_or_not(request, ctx)


@login_required
def subject_attendance(request, idsubj):
    """
    Devuelve la pagina con la informacion de la asistencia de los
    alumnos a una asignatura
    """
    if request.method != 'GET':
        return method_not_allowed(request)

    try:
        subject = Subject.objects.get(id=idsubj)
    except Subject.DoesNotExist:
        return send_error_page(request, 'La asignatura con id ' + str(idsubj) +
                               ' no existe.')

    if not request.user.has_perm('app.can_see_statistics'):
        try:
            profile = request.user.userprofile
        except UserProfile.DoesNotExist:
            return send_error_page(request, 'No tienes un perfil creado.')
        if profile.is_student:
            return send_error_page(request,
                                   'Solo los profesores tienen acceso.')
        if not subject in profile.subjects.all():
            return send_error_page(request,
                                 'No tienes acceso a esta informaci&oacute;n.')
    
    students = subject.userprofile_set.filter(is_student=True)
    lessons = subject.lesson_set.filter(done=True)
    n_lessons = lessons.count()
    checkins = CheckIn.objects.filter(lesson__in = lessons)
    students_info = []
    for student in students:
        if n_lessons > 0:
            n_checkins = checkins.filter(user=student.user).count()
            percent = round(100.0 * n_checkins / n_lessons, 2)
        else:
            percent = 0
        students_info.append({'id': student.user.id, 'percent': percent,
                              'name': student.user.first_name + ' ' +
                              student.user.last_name, 'dni': student.dni})
        
    ctx = {'students': students_info, 'subject': subject,
           'htmlname': 'subject_attendance.html'}
    return response_ajax_or_not(request, ctx)


@login_required
def subject_edit(request, idsubj):
    """Devuelve la pagina para editar o eliminar una asignatura"""
    if request.method != 'GET' and request.method != 'POST':
        return method_not_allowed(request)

    try:
        subject = Subject.objects.get(id=idsubj)
        if subject.creator != request.user:
            return send_error_page(request, 'Solo el creador de la ' + 
                                   'asignatura puede editarla.')
    except Subject.DoesNotExist:
        return send_error_page(request, 'La asignatura con id ' + str(idsubj) +
                               ' no existe.')

    if request.method == 'POST':
        resp = False
        if request.POST.get("action", default='edit') == 'delete':
            subject.delete()
            if request.is_ajax():
                resp = HttpResponse(json.dumps({'deleted': True,
                                                'redirect': '/subjects'}),
                                    content_type="application/json")
            else:
                resp = HttpResponseRedirect('/subjects')
        else:
            sform = SubjectForm(request.POST, instance=subject)
            if sform.is_valid():
                sform.save()
                if request.is_ajax():
                    resp = HttpResponse(json.dumps({'ok': True}),
                                        content_type="application/json")
            elif request.is_ajax():
                resp = HttpResponse(json.dumps({'errors': sform.errors}), 
                                    content_type="application/json")
        if resp:
            return resp
    else:
        sform = SubjectForm(instance=subject)
    ctx = {'subject': subject, 'form': sform, 'htmlname': 'subject_edit.html'}
    return response_ajax_or_not(request, ctx)


@login_required
def create_lesson(request, idsubj):
    """Devuelve la pagina para crear una clase"""
    if request.method != 'GET' and request.method != 'POST':
        return method_not_allowed(request)

    try:
        profile = request.user.userprofile
        if profile.is_student:
            return send_error_page(request,
                                   'Solo los profesores tienen acceso.')
        subject = profile.subjects.get(id=idsubj)
    except UserProfile.DoesNotExist:
        return send_error_page(request, 'No tienes un perfil creado.')
    except Subject.DoesNotExist:
        return send_error_page(request, 'No eres profesor de la asignatura ' +
                               'con id ' + str(idsubj))

    if request.method == 'POST':
        lesson = Lesson(is_extra=True, subject=subject)
        lform = ExtraLessonForm(request.POST, instance=lesson)
        resp = False
        if lform.is_valid():
            lesson = lform.save()
            if request.is_ajax():
                resp = HttpResponse(json.dumps({'ok': True,
                                    'redirect': '/lesson/' + str(lesson.id)}), 
                                    content_type="application/json")
            else:
                resp = HttpResponseRedirect('/lesson/' + str(lesson.id))
        elif request.is_ajax():
            resp = HttpResponse(json.dumps({'errors': lform.errors}), 
                                content_type="application/json")
        if resp:
            return resp
    else:
        lform = ExtraLessonForm()
    ctx = {'subject': subject, 'form': lform, 'room_form': FreeRoomForm(),
           'htmlname': 'new_lesson.html'}
    return response_ajax_or_not(request, ctx)


def delete_lesson(request, lesson):
    """Borra una clase si es extra y redirecciona a la asignatura"""
    if lesson.is_extra:
        url_redirect = '/subjects/' + str(lesson.subject.id)
        lesson.delete()
        if request.is_ajax():
            return HttpResponse(json.dumps({'deleted': True,
                                            'redirect': url_redirect}),
                                content_type="application/json")
        return HttpResponseRedirect(url_redirect)
    else:
        return send_error_page(request,
                               'Solo se pueden eliminar clases extras')

def edit_lesson(request, idlesson):
    """Devuelve la pagina para editar o eliminar una clase"""
    if request.method != 'GET' and request.method != 'POST':
        return method_not_allowed(request)

    try:
        profile = request.user.userprofile
        if profile.is_student:
            return send_error_page(request,
                                   'Solo los profesores tienen acceso.')
        lesson = Lesson.objects.get(id=idlesson)
        if lesson.start_time < timezone.now():
            return send_error_page(request,
                                   'No se pueden editar clases antiguas.')
        if lesson.subject not in profile.subjects.all():
            return send_error_page(request, 'Tienes que ser profesor de la ' +
                                   'asignatura para editarla.')
    except UserProfile.DoesNotExist:
        return send_error_page(request, 'No tienes un perfil creado.')
    except Lesson.DoesNotExist:
        return send_error_page(request, 'No existe ninguna clase con id ' +
                                str(idlesson))

    if request.method == 'POST':
        if request.POST.get("action", default='edit') == 'delete':
            return delete_lesson(request, lesson)

        lform = ExtraLessonForm(request.POST, instance=lesson)           
        if lform.is_valid():
            lform.save()
            if request.is_ajax():
                return HttpResponse(json.dumps({'ok': True}),
                                    content_type="application/json")
        elif request.is_ajax():
            return HttpResponse(json.dumps({'errors': lform.errors}), 
                                content_type="application/json")
    else:
        lform = ExtraLessonForm(instance=lesson)
    ctx = {'lesson': lesson, 'form': lform, 'room_form': FreeRoomForm(),
           'htmlname': 'lesson_edit.html'}
    return response_ajax_or_not(request, ctx)


@login_required
def free_room(request):
    """
    Devuelve un aula libre en la franja horaria solicitada y en el
    edificio solicitado
    """
    if request.method != 'GET':
        return method_not_allowed(request)
    form = FreeRoomForm(request.GET)
    f_room = False
    if form.is_valid():
        data = form.cleaned_data
        f_room = get_free_room(data['start_time'], data['end_time'],
                               data['building'])
        if not f_room:
            f_room = 'No hay aulas libres en el ' + str(data['building'])
        if request.is_ajax():
            return HttpResponse(json.dumps({'ok': True,
                                            'free_room': str(f_room)}), 
                                content_type="application/json")
    elif request.is_ajax():
        return HttpResponse(json.dumps({'ok': False, 'errors': form.errors}), 
                            content_type="application/json")
    ctx = {'room_form': form, 'free_room': f_room,
           'htmlname': 'freeroom.html'}
    return response_ajax_or_not(request, ctx)


@login_required
def reports_page(request):
    """
    Devuelve una pagina con un formulario para reportar un problema a
    los administradores y muestra el estado de los ultimos reportes del
    usuario
    """
    if request.method != 'GET' and request.method != 'POST':
        return method_not_allowed(request)

    if request.method == 'POST':
        report = AdminTask(user=request.user)
        form = ReportForm(request.POST, instance=report)
        if not form.is_valid():
            if request.is_ajax():
                return HttpResponse(json.dumps({'errors': form.errors}), 
                                    content_type="application/json")
        else:
            report = form.save()
            if request.is_ajax():
                html = loader.get_template('pieces/reports.html').render(\
                                RequestContext(request, {'reports':[report]}))
                resp = {'report':html, 'ok': True, 'idreport': report.id}
                return HttpResponse(json.dumps(resp),
                                    content_type="application/json")
            else:
                form = ReportForm()

    if request.method != 'POST':
        form = ReportForm()
    reports = my_paginator(
        request, AdminTask.objects.filter(user=request.user).order_by('-time'),
        10)
    ctx = {'form': form, 'reports': reports, 'htmlname': 'reports.html'}
    return response_ajax_or_not(request, ctx)

@login_required
def control_attendance(request):
    """
    Devuelve una pagina para comprobar si las clases se estan realizando
    """
    if request.method != 'GET':
        return method_not_allowed(request)
    if not request.user.has_perm('app.can_see_statistics'):
        return send_error_page(request, 'No tienes permisos para ver esta ' +
                                'informaci&oacute;n.')

    form = ControlFilterForm(request.GET)
    all_subj = control_order(form, control_filter(form))
    subjects = my_paginator(request, all_subj, 10)
    subjects_wrap = []
    for subject in subjects:
        element =  {'professors': subject.userprofile_set.filter(\
                    is_student=False), 'subject': subject}
        subjects_wrap.append(element)
    url_page = prepare_url_pagination(request.get_full_path())
    ctx = {'form': form, 'rows': subjects_wrap, 'subjects': subjects, 
           'htmlname': 'control_attendance.html', 'url_page': url_page}
    return response_ajax_or_not(request, ctx)

    

def prepare_url_pagination(full_url):
    """
    Devuelve la url lista para poner el numero de pagina manteniendo la
    querystring en caso de que la hubiese
    """
    url = full_url
    if 'page=' in full_url:
        #elimina '?page=X' o '&page=X'
        url = full_url[:full_url.index('page=')-1]

    if '?' in url:
        url = url + '&page='
    else:
        url = url + '?page='

    return url


def control_filter(form):
    """
    Filtra las asignaturas por nombre, profesor y grado segun el form
    del tipo ControlFilterForm
    """
    all_subj = Subject.objects.all()
    if not form.is_valid():
        return all_subj
    data = form.cleaned_data

    f_type = data['subject_type']    
    if f_type == 'Sem':
        all_subj = all_subj.filter(is_seminar=True)
    elif f_type == 'Subj':
        all_subj = all_subj.filter(is_seminar=False)

    f_subject = data['subject']
    if len(f_subject) > 0:
        all_subj = all_subj.filter(name__contains=f_subject)

    f_degree = data['degree']
    if len(f_degree) > 0:
        all_subj = all_subj.filter(degrees__name__contains=f_degree).distinct()

    f_prof_0 = data['professor_0']
    if len(f_prof_0) > 0:
        all_subj = all_subj.filter(
                userprofile__is_student=False,
                userprofile__user__first_name__contains=f_prof_0).distinct()

    f_prof_1 = data['professor_1']
    if len(f_prof_1):
        all_subj = all_subj.filter(
                    userprofile__is_student=False,
                    userprofile__user__last_name__contains=f_prof_1).distinct()

    return all_subj

def control_order(form, subjects):
    """
    Ordena las asignaturas por nombre, fecha de inicio o fecha de
    finlaizacion
    """
    if form.is_valid():
        data = form.cleaned_data
        order = data['order']
        if data['order_reverse']:
            order = '-' + order
    else:
        order = 'name'
    return subjects.order_by(order)


@login_required
def show_codes(request):
    """Devuelve una pagina con los codigos para hacer checkin"""
    if request.method != 'GET':
        return method_not_allowed(request)
    if not request.user.has_perm('app.can_see_codes'):
        return send_error_page(request, 'No tienes permisos para ver esta ' +
                               'informaci&oacute;n.')
    form = CodesFilterForm(request.GET)
    all_lessons = codes_order(form, codes_filter(form))

    ctx = {'form': form, 'htmlname': 'control_codes.html',
           'lessons': all_lessons}
    return response_ajax_or_not(request, ctx)


def codes_order(form, lessons):
    """Ordena las clases por fecha de inicio, aula o edificio"""
    if not lessons or not form.is_valid:
        return lessons
    
    data = form.cleaned_data
    order = data['order']
    if data['order_reverse']:
        order = '-' + order
    return lessons.order_by(order)


def codes_filter(form):
    """
    Filtra las clases por dia, aula, edificio y tipo de Subject segun el
    form del tipo CodesFilterForm
    """
    if not form.is_valid():
        return {}
    all_lessons = Lesson.objects.all()
    data = form.cleaned_data
    f_type = data['subject_type']    
    if f_type == 'Sem':
        all_lessons = all_lessons.filter(subject__is_seminar=True)
    elif f_type == 'Subj':
        all_lessons = all_lessons.filter(subject__is_seminar=False)

    f_date = data['day']
    f_from = data['from_time']
    f_to = data['to_time']
    #Las horas son naive, y estan relacionadas con la hora local del usuario
    #que solicita los codigos por eso se las localiza con la timezone local
    f_from_dt = datetime.datetime(f_date.year, f_date.month, f_date.day,
                                  f_from.hour, f_from.minute)
    f_from_dt = pytz.timezone(str(timezone.get_current_timezone())).localize(\
                                                        f_from_dt, is_dst=None)
    f_to_dt = datetime.datetime(f_date.year, f_date.month, f_date.day,
                                f_to.hour, f_to.minute)
    f_to_dt = pytz.timezone(str(timezone.get_current_timezone())).localize(\
                                                        f_to_dt, is_dst=None)
    
    all_lessons = all_lessons.filter(start_time__lte = f_to_dt,
                                     start_time__gte = f_from_dt)

    f_room = data['room']
    f_building = data['building']
    if f_room:
        all_lessons = all_lessons.filter(room=f_room)
    elif f_building:
        all_lessons = all_lessons.filter(room__building=f_building)
    return all_lessons
    
@login_required
def email_change(request):
    """
    Modifica el email del usuario que realiza la peticion
    Si la peticion es ajax devuelve el resultado de la peticion y si no es ajax
    redirige al usuario a su perfil
    """
    if request.method != 'POST':
        return method_not_allowed(request)
    eform = ChangeEmailForm(request.POST, instance=request.user)
    if eform.is_valid():
        eform.save()
        if request.is_ajax():
            resp = {'ok': True, 'email': request.user.email}
            return HttpResponse(json.dumps(resp),
                                content_type="application/json")
    else:
        if request.is_ajax():
            resp = {'ok': False, 'errors': eform.errors}
            return HttpResponse(json.dumps(resp),
                                content_type="application/json")
    return HttpResponseRedirect('/profile/view/' + str(request.user.id))

    
########################################################
# Funciones para solicitar mas elementos de algun tipo #
########################################################
def get_lesson_comments(request, idlesson):
    """
    Devuelve todos los comentarios de la clase con id idlesson si el
    usuario tiene permiso para verlos (esta relacionado con la
    asignatura o con permiso can_see_statistics)
    En caso de error devuelve False
    """
    try:
        lesson = Lesson.objects.get(id=idlesson)
        profile = request.user.userprofile
        if not lesson.subject in profile.subjects.all():
            return False
    except Lesson.DoesNotExist:
        return False
    except UserProfile.DoesNotExist:
        if not request.user.has_perm('app.can_see_statistics'):
            return False
    return LessonComment.objects.filter(lesson=lesson)


def get_more_comments_threshold(is_lesson, idcurrent):
    """
    Devuelve el momento de publicacion del comentario idcurrent
    Si is_lesson es True lo busca en LessonComment y en caso contrario
    en ForumComment
    Si no existe el comentario devuelve False, y si idcurrent es menor
    que 0 devuelve el dia anterior a la hora actual
    """
    if idcurrent > 0:
        try:
            if is_lesson:
                comment = LessonComment.objects.get(id=idcurrent)
            else:
                comment = ForumComment.objects.get(id=idcurrent)
        except (ForumComment.DoesNotExist, LessonComment.DoesNotExist):
            return False
        current_date = comment.date
    else: #Para el caso en el que no hubiese ningun mensaje en la pagina
        current_date = timezone.now() - datetime.timedelta(days=1)
    return current_date


@login_required
@ajax_required
def more_comments(request, current, idlesson, newer):
    """
    Si newer = True devuelve un fragmento html con 10 comentarios mas
    nuevos que num ordenados de mas nuevo a mas antiguo. Si newer = 
    False los anteriores.
    Ademas indica si son newer y el id del mas reciente/mas antiguo (si
    no hay devuelve 0)
    Si idlesson es menor que 1 los coge del foro y si no de la lesson
    con id idlesson
    """
    current = int(current)
    idlesson = int(idlesson)
    newer = (newer == 'true')
    current_date = get_more_comments_threshold(idlesson > 0, current)
    if not current_date:
        resp = {'comments': [], 'idcomment': 0, 'newer': True}
        return HttpResponse(json.dumps(resp),
                            content_type="application/json")
        
    if idlesson > 0:
        all_comments = get_lesson_comments(request, idlesson)
        if not all_comments:
            resp = {'comments': [], 'idcomment': 0, 'newer': True}
            return HttpResponse(json.dumps(resp),
                                    content_type="application/json")
    else:
        all_comments = ForumComment.objects.all()

    if newer:
        comments = all_comments.filter(date__gt=current_date).order_by('-date')
        #Se tiene que hacer asi porque si se hace el slice primero con
        #order_by('date') y luego se llama a reverse() se seleccionan los 10 
        #elementos opuestos
        n_comments = comments.count()
        if n_comments > 10:
            comments = comments[n_comments-10:]
    else:
        comments = all_comments.filter(date__lt=current_date).order_by(\
                                                                '-date')[0:10]
    if comments:
        if newer:
            idcomment = comments[0].id
        else:
            idcomment = comments[comments.count()-1].id
    else:
        idcomment = 0
    html = loader.get_template('pieces/comments.html').render(\
                                RequestContext(request, {'comments':comments}))
    resp = {'comments':html, 'newer':newer, 'idcomment':idcomment,
            'idlesson':idlesson}
    return HttpResponse(json.dumps(resp), content_type="application/json")


@login_required
@ajax_required
def more_lessons(request, current, newer):
    """
    Si newer = True devuelve un fragmento html con 10 clases posteriores
    a la lesson con id current ordenados de menor fecha a mayor fecha.
    Si newer = False las anteriores ordenadas de mayor fecha a menos
    fecha.
    Ademas indica si son newer y el id de la ultima lesson que devuelve
    (si no hay devuelve 0)
    """
    current = int(current)
    newer = (newer == 'true')
    try:
        lesson = Lesson.objects.get(id=current)
        subject = lesson.subject
    except Lesson.DoesNotExist:
        resp = {'lessons': [], 'newer': newer, 'idlesson': 0}
        return HttpResponse(json.dumps(resp), content_type="application/json")
    #no tiene acceso a asignaturas que no tiene (a no ser que tenga permiso
    #can_see_statistics)
    if not (request.user.has_perm('app.can_see_statistics') or 
                                                subject.is_seminar):
        try:
            profile = request.user.userprofile
        except UserProfile.DoesNotExist:
            resp = {'lessons': [], 'newer': newer, 'idlesson': 0}
            return HttpResponse(json.dumps(resp),
                                content_type="application/json")
        if not subject in profile.subjects.all():
            resp = {'lessons': [], 'newer': newer, 'idlesson': 0}
            return HttpResponse(json.dumps(resp),
                                content_type="application/json")

    all_lessons = Lesson.objects.filter(subject=subject.id)
    if newer:
        lessons = all_lessons.filter(end_time__gt=lesson.end_time).\
                                                order_by('end_time')[0:10]
    else:
        lessons = all_lessons.filter(start_time__lt=lesson.start_time).\
                                                order_by('-start_time')[0:10]
    if lessons:
        idlesson = lessons[lessons.count()-1].id
    else:
        idlesson = 0
    html = loader.get_template('pieces/lessons.html').render(RequestContext(
                                request, {'lessons':lessons, 'future':newer}))
    resp = {'lessons': html, 'newer': newer, 'idlesson': idlesson}
    return HttpResponse(json.dumps(resp), content_type="application/json")


@login_required
@ajax_required
def more_reports(request, current, newer):
    """
    Si newer = True devuelve un fragmento html con los 10 reportes mas
    recientes que el reporte current ordenados de mas reciente a mas
    antiguo. Si newer = False los anteriores a current.
    Ademas indica si son newer y el id del mas reciente/mas antiguo (si
    no hay devuelve 0)
    """
    current = int(current)
    newer = (newer == 'true')
    try:
        report = AdminTask.objects.get(id=current)
    except AdminTask.DoesNotExist:
        resp = {'reports': [], 'newer': newer, 'idreport': 0}
        return HttpResponse(json.dumps(resp), content_type="application/json")

    all_reports = AdminTask.objects.filter(user=request.user)
    if newer:
        reports = all_reports.filter(time__gt=report.time).order_by('-time')
        #Se tiene que hacer asi porque si se hace el slice primero con
        #order_by('time') y luego se llama a reverse() se seleccionan los 10
        #elementos opuestos
        n_reports = reports.count()
        if n_reports > 10:
            reports = reports[n_reports-10:]
    else:
        reports = all_reports.filter(time__lt=report.time).\
                                                    order_by('-time')[0:10]

    if reports:
        if newer:
            idreport = reports[0].id
        else:
            idreport = reports[reports.count()-1].id
    else:
        idreport = 0
    html = loader.get_template('pieces/reports.html').render(RequestContext(
                                                request, {'reports':reports}))
    resp = {'reports':html, 'newer':newer, 'idreport':idreport}
    return HttpResponse(json.dumps(resp), content_type="application/json")

