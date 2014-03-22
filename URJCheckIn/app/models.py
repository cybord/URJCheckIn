from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.db.models import Avg

WEEK_DAYS = (
	('Mon', 'Monday'),
	('Tue', 'Tuesday'),
	('Wed', 'Wednesday'),
	('Thu', 'Thursday'),
	('Fri', 'Friday'),
	('Sat', 'Saturday'),
	('Sun', 'Sunday')
)
FIRST_ADMIN_ID = 1

class Degree(models.Model):
	name = models.CharField(max_length=100, unique=True, verbose_name='nombre')
	code = models.CharField(max_length=6, unique=True, verbose_name='codigo')

	class Meta:
		verbose_name='grado'

	def __unicode__(self):
		return self.code

class Subject(models.Model):
	name = models.CharField(max_length=100, verbose_name='nombre')
	degrees = models.ManyToManyField(Degree, verbose_name='grados')
	first_date = models.DateField(verbose_name='fecha de inicio')
	last_date = models.DateField(verbose_name='fecha de finalizacion')
	is_seminar = models.BooleanField(verbose_name='es seminario', default=False)
	#util para seminarios, se puede dejar a 0 para clases
	max_students = models.PositiveIntegerField(verbose_name='plazas', default=0)
	description = models.TextField(max_length=200, blank=True, verbose_name='descripcion')
	creator = models.ForeignKey(User, verbose_name='creador', default=FIRST_ADMIN_ID)

	class Meta:
		verbose_name = 'asignatura'
	
	def __unicode__(self):
		return u"%s" % (self.name)

	def clean(self):
		super(Subject, self).clean()
		if self.first_date and self.last_date:
			if (self.first_date > self.last_date):
				raise ValidationError('First_date can not be greater than last_date')

	def n_students(self):
		return self.userprofile_set.filter(is_student=True).count()


class Room(models.Model):
	room = models.CharField(max_length=20, verbose_name='aula')
	building = models.CharField(max_length=20, verbose_name='edificio')
	centre_longitude = models.IntegerField(verbose_name='centro longitud')
	centre_latitude = models.IntegerField(verbose_name='centro latitud')
	radius = models.IntegerField(verbose_name='radio')

	class Meta:
		verbose_name='aula'
		unique_together = ("room", "building")

	def __unicode__(self):
		return u"Aula %i" % (self.id)


class UserProfile(models.Model):
	user = models.OneToOneField(User, verbose_name='usuario')
	photo = models.ImageField(upload_to='profile_photos', blank=True)#Poner una por defecto (la tipica silueta)
	description = models.TextField(max_length=200, blank=True, verbose_name='descripcion')
	subjects = models.ManyToManyField(Subject, blank=True, verbose_name='asignatura')
	degrees = models.ManyToManyField(Degree, blank=True, verbose_name='grados')
	#TODO si se introduce una asignatura(+profesor) se debe poner el degree si no estaba
	is_student = models.BooleanField(default=True, verbose_name='es alumno')
	age = models.PositiveIntegerField(validators=[MinValueValidator(17), MaxValueValidator(100)], verbose_name='edad', blank=True)
	#TODO quizas mejor poner como grupo de usuario
	dni = models.CharField(max_length=20, verbose_name='DNI (o similar)')

	class Meta:
		verbose_name='perfil de usuario'
		verbose_name_plural='perfiles de usuario'
	
	def __unicode__(self):
		return u"Perfil de %s" % (self.user)

	

class Lesson(models.Model):
	start_time =  models.DateTimeField(verbose_name='hora de inicio')
	end_time = models.DateTimeField(verbose_name='hora de finalizacion')
	subject = models.ForeignKey(Subject, verbose_name='asignatura')
	room =	models.ForeignKey(Room, verbose_name='aula')#TODO on_delete funcion para buscar otra aula
	is_extra = models.BooleanField(default=False, verbose_name='es clase extra')
	
	class Meta:
		verbose_name='clase'

	def __unicode__(self):
		return u"Clase de %s" % (self.subject)
	
	def clean(self):
		super(Lesson, self).clean()
		if self.start_time and self.end_time:
			if self.start_time < timezone.now():
				raise ValidationError('Start_time must be greater than now')
			if self.start_time >= self.end_time:
				raise ValidationError('End_time must me greater than start_time')
			#Para evitar solapamiento de clases
			lesson_same_time = Lesson.objects.exclude(
						start_time__gte=self.end_time
					).exclude(
						end_time__lte=self.start_time
					).exclude(
						id=self.id
					)
			try:
				if lesson_same_time.filter(subject=self.subject):
					raise ValidationError('The lesson can not coincide with ' +
											'another of the same subject')
				if lesson_same_time.filter(room=self.room):
					raise ValidationError('The lesson can not coincide with ' +
											'another in the same room')
			except (Subject.DoesNotExist, Room.DoesNotExist):
				pass

	def checkin_percent(self):
		n_students = self.subject.n_students()
		if n_students > 0:
			n_checkin = self.checkin_set.filter(user__userprofile__is_student=True).count()
			return round(100.0*n_checkin/n_students,2)
		else:
			return 100

	def avg_mark(self):
		checkins = self.checkin_set.filter(user__userprofile__is_student=True)
		print checkins
		if not checkins:
			return 3
		mark = checkins.aggregate(Avg('mark'))['mark__avg']
		return round(mark,2)

class CheckIn(models.Model):
	user = models.ForeignKey(User, verbose_name='usuario')
	lesson = models.ForeignKey(Lesson, verbose_name='clase')
	mark = models.PositiveIntegerField(validators=[MaxValueValidator(5)], verbose_name='puntuacion', blank=True)
	comment = models.TextField(max_length=250, verbose_name='comentario', blank=True)

	class Meta:
		unique_together = ("user", "lesson")

	def __unicode__(self):
		return u"Checkin de %s" % (self.lesson)


class LessonComment(models.Model):
	user = models.ForeignKey(User, verbose_name='usuario')
	lesson = models.ForeignKey(Lesson, verbose_name='clase')
	date =  models.DateTimeField(default=timezone.now, verbose_name='hora')
	comment = models.TextField(max_length=250, verbose_name='comentario')
	is_extra = models.BooleanField(verbose_name='clase extra', default=False)
	
	class Meta:
		verbose_name='comentario en clase'
		verbose_name_plural='comentarios en clase'

	def __unicode__(self):
		return u"Comentario de %s" % (self.lesson)


class ForumComment(models.Model):
	user = models.ForeignKey(User, verbose_name='usuario')
	comment = models.TextField(max_length=150, verbose_name='comentario')
	date =  models.DateTimeField(default=timezone.now, verbose_name='hora')

	class Meta:
		verbose_name='comentario del foro'
		verbose_name_plural='comentarios del foro'

	def __unicode__(self):
		return u"Comentario %i" % (self.id)


class Timetable(models.Model):
	subject = models.ForeignKey(Subject, verbose_name='asignatura')
	day = models.CharField(max_length=3, choices=WEEK_DAYS)
	start_time =  models.TimeField(verbose_name='hora de inicio')
	end_time = models.TimeField(verbose_name='hora de finalizacion')
	room =	models.ForeignKey(Room, verbose_name='aula')#TODO on_delete decidir que hago
	#Posible solucion poner edificio por si el aula no esta disponible
	#TODO No se si poner profesor o nada y que sean todos los de la asignatura
	
	class Meta:
		verbose_name='horario'

	def __unicode__(self):
		return u"Horario de %s" % (self.subject)

	def clean(self):
		super(Timetable, self).clean()
		if self.start_time and self.end_time and self.day:
			if (self.start_time >= self.end_time):
				raise ValidationError('End_time must me greater than start_time')
			#Para evitar solapamiento de clases
			timetables_same_time = Timetable.objects.filter(
							day=self.day
						).exclude(
							start_time__gte=self.end_time
						).exclude(
							end_time__lte=self.start_time
						).exclude(
							id=self.id
						)
			try:
				if timetables_same_time.filter(subject=self.subject):
					raise ValidationError('The timetable can not coincide with \
											another of the same subject')
				if timetables_same_time.filter(room=self.room):
					raise ValidationError('The timetable can not coincide with \
											another in the same room')
			except (Subject.DoesNotExist, Room.DoesNotExist):
				pass
	#TODO despues de guardar hay que crear las clases



