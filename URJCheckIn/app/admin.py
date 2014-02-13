from django.contrib import admin
from models import Degree, Subject, Room, StudentProfile, TeacherProfile, ClassReview, Lesson, CheckIn, ForumComment

admin.site.register(Degree)
admin.site.register(Subject)
admin.site.register(Room)
admin.site.register(StudentProfile)
admin.site.register(TeacherProfile)
admin.site.register(ClassReview)#no deberian poder cambiarlo los administradores
admin.site.register(Lesson)
admin.site.register(CheckIn)
admin.site.register(forumComment)#no deberían poder poner nuevos o modificarlos, solo borrarlos
