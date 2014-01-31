from django.utils import simplejson
from dajaxice.decorators import dajaxice_register
from django.template import loader, Context
from forms import ReviewClassForm, ProfileEditionForm

from django.utils.datastructures import MultiValueDictKeyError


@dajaxice_register(method='GET')
def profile(request, iduser):
	"""Devuelve el contenido de la pagina de perfil"""
	if request.method == "GET":
		templ = loader.get_template('profile.html')
		cont = Context({'user': {'name':iduser, 'student': False, 'id':iduser}, 
						'classes': [{'id':'idclase1', 'name':'clase1'}, {'id':'idclase2', 'name':'clase2'}],
						'form': ProfileEditionForm()})
		html = templ.render(cont)
		return simplejson.dumps({'#mainbody':html, 'url': '/profile/view/'+iduser})
	else:
		return wrongMethodJson(request)


@dajaxice_register(method='POST')
def update_profile(request, iduser, form):
	"""Modifica el perfil del usuario registrado"""
	if request.method == "POST":
		#comprobar user = usuarioregistrado
		pform = ProfileEditionForm(form)
		if not pform.is_valid():
			return simplejson.dumps({'error': form.errors});
		data = pform.cleaned_data
		return simplejson.dumps({'user':{'id': iduser, 'age':data['age']}})#coger datos del usuario tras guardar
	else:
		return wrongMethodJson(request)


@dajaxice_register(method='POST')#quitar POSTs si son por defecto
def process_class(request,form):#TODO mirar el campo class del form
	if request.method == "POST":
		return simplejson.dumps({'deleteFromDOM':['#xc_'+form['idclass']]})
	else:
		return wrongMethodJson(request)

@dajaxice_register(method='GET')
def checkin(request):
	"""Devuelve la pagina para hacer check in"""
	if request.method == "GET":
		html = loader.get_template('checkin.html').render(Context({}))
		print html
		return simplejson.dumps({'#mainbody':html, 'url': '/checkin'})
	else:
		return wrongMethodJson(request)

@dajaxice_register(method='POST')#quitar POSTs si son por defecto
def process_checkin(request, form):
	""" procesa un check in"""
	if request.method == "POST":
		print form["longitude"]
		print form["latitude"]
		print form["accuracy"]
		print form["codeword"]
		return simplejson.dumps({'ok': True})
	else:
		return wrongMethodJson(request)

def wrongMethodJson(request):
	return simplejson.dumps({'error':'Metodo ' + request.method + ' no soportado'})


