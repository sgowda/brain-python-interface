from django.conf.urls.defaults import *

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
	(r'^$', 'tracker.views.list'),
    (r'^ajax/task_params/(?P<taskname>\w+)/', 'tracker.ajax.task_params'),
    (r'^ajax/task_seq/(?P<idx>\d+)/', "tracker.ajax.task_seq"),
    (r'^ajax/exp_info/(?P<idx>\d+)/', 'tracker.ajax.exp_info'),
    (r'^ajax/seq_data/(?P<idx>\d+)/', 'tracker.ajax.seq_data'),
    # Uncomment the admin/doc line below to enable admin documentation:
    (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    (r'^admin/', include(admin.site.urls)),
)