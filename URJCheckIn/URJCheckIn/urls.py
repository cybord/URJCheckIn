from django.conf.urls import patterns, include, url
from django.conf import settings

# The next two lines enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', 'app.views.home', name='home'),
    url(r'^checkin$', 'app.views.checkin_page', name='checkin'),
    url(r'^help$', 'app.views.help_page', name='help'),
    url(r'^profile/view/(?P<iduser>\d+)$', 'app.views.profile_page',
        name='profile'),
    url(r'^profile/img/(?P<action>edit|delete)$',
        'app.views.change_profile_img', name='change_profile_img'),
    url(r'^lesson/(?P<idlesson>\d+)$', 'app.views.process_lesson',
        name='process_lesson'),
    url(r'^lesson/(?P<idlesson>\d+)/attendance$',
        'app.views.lesson_attendance', name='lesson_attendance'),
    url(r'^lesson/(?P<idlesson>\d+)/edit$', 'app.views.edit_lesson',
        name='edit_lesson'),
    url(r'^freeroom$', 'app.views.free_room', name='get_free_room'),
    url(r'^forum$', 'app.views.forum', name='forum'),
    url(r'^subjects$', 'app.views.subjects_page', name='subjects'),
    url(r'^seminars$', 'app.views.seminars', name='seminars'),
    url(r'^subjects/(?P<idsubj>\d+)$', 'app.views.subject_page',
        name='subject'),
    url(r'^subjects/(?P<idsubj>\d+)/attendance$',
        'app.views.subject_attendance', name='subject_attendance'),
    url(r'^subjects/(?P<idsubj>\d+)/edit$', 'app.views.subject_edit',
        name='subject_edit'),
    url(r'^subjects/(?P<idsubj>\d+)/new_lesson$', 'app.views.create_lesson',
        name='create_lesson'),
    url(r'^subjects/(?P<idsubj>\d+)/statistics$',
        'app.views.subject_statistics', name='subject_statistics'),
    url(r'^img/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root': 'static/images'}),
    url(r'^media/(?P<path>.*)$', 'django.views.static.serve', 
        {'document_root': settings.MEDIA_ROOT}),
    url(r'^css/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root': 'static/css'}),
    url(r'^jscript/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root': 'static/javascript'}),
    url(r'^lib/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root': 'lib'}),
    url(r'^csv/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root': 'static/csv'}),
    url(r'^pdf/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root': 'static/pdf'}),
    url(r'^firefoxos/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root': 'static/firefoxos'}),
    url(r'reports$', 'app.views.reports_page', name='reports'),
    url(r'more/reports/(?P<current>\d+)/(?P<newer>true|false)$',
        'app.views.more_reports', name='more_reports'),
    url(r'more/comments/(?P<current>\d+)/(?P<idlesson>\d+)/(?P<newer>true|false)$', 
        'app.views.more_comments', name='more_comments'),
    url(r'more/lessons/(?P<current>\d+)/(?P<newer>true|false)$',
        'app.views.more_lessons',  name='more_lessons'),
    url(r'control/attendance$', 'app.views.control_attendance',
        name='control_attendance'),
    url(r'control/codes$', 'app.views.show_codes', name='show_codes'),
    url(r'^logout$', 'app.views.my_logout', name='my_logout'),
    url(r'^login$', 'django.contrib.auth.views.login'),
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/auth/user/csv/', 'app.admin_csv.create_users',
        name='csv_create_users'),
    url(r'^admin/app/subject/(?P<idsubj>\d+)/csv/',
        'app.admin_csv.relate_subject_user', name='csv_relate_subject_user'),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^email_change$', 'app.views.email_change', name='email_change'),
    url(r'^password_change/ajax$', 'app.views.password_change',
        name='my_password_change'),
    url(r'^password_change/$', 'django.contrib.auth.views.password_change'),
    url(r'^password_change/done/$',
        'django.contrib.auth.views.password_change_done'),
    url(r'^password_reset/$', 'django.contrib.auth.views.password_reset'),
    url(r'^password_reset/done/$',
        'django.contrib.auth.views.password_reset_done'),
    url(r'^reset/(?P<uidb36>[0-9A-Za-z]+)-(?P<token>.+)/$',
        'django.contrib.auth.views.password_reset_confirm'),
    url(r'^reset/done/$', 'django.contrib.auth.views.password_reset_complete'),
    url(r'^.*$', 'app.views.not_found'),
)

