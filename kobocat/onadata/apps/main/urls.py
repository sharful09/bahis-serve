import debug_toolbar

from django.conf.urls import patterns, include, url
from django.conf import settings
from django.views.generic import RedirectView

from onadata.apps.api.urls import router, router_with_patch_list
from onadata.apps.api.urls import XFormListApi
from onadata.apps.api.urls import XFormSubmissionApi
from onadata.apps.api.urls import BriefcaseApi

# Uncomment the next two lines to enable the admin:
from django.contrib import admin

admin.autodiscover()

urlpatterns = patterns(
    '',
    # change Language
    (r'^i18n/', include('django.conf.urls.i18n')),
    url('^api/v1/', include(router.urls)),
    url('^api/v1/', include(router_with_patch_list.urls)),
    url(r'^service_health/$',
        'onadata.apps.main.service_health.service_health'),
    url(r'^api-docs/', RedirectView.as_view(url='/api/v1/')),
    url(r'^api/', RedirectView.as_view(url='/api/v1/')),
    url(r'^api/v1', RedirectView.as_view(url='/api/v1/')),

    # django default stuff
    url(r'^accounts/', include('onadata.apps.main.registration_urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # oath2_provider
    url(r'^o/', include('oauth2_provider.urls', namespace='oauth2_provider')),

    # google urls
    url(r'^gauthtest/$',
        'onadata.apps.main.google_export.google_oauth2_request',
        name='google-auth'),
    url(r'^gwelcome/$',
        'onadata.apps.main.google_export.google_auth_return',
        name='google-auth-welcome'),
    url(r'^usermodule/', include('onadata.apps.usermodule.urls', namespace="usermodule")),
    url(r'^bhmodule/', include('onadata.apps.bh_module.urls', namespace="bh_module")),
    url(r'^formmodule/', include('onadata.apps.formmodule.urls', namespace="formmodule")),
    url(r'^reportsmodule/', include('onadata.apps.reportsmodule.urls', namespace="reportsmodule")),
    # main website views
    url(r'^$', 'onadata.apps.main.views.survey_summary'),
    url(r'^add/(?P<id_string>[^/]+)/$', 'onadata.apps.main.views.add_form', name='add_form'),
    url(r'^form_designer/$','onadata.apps.main.views.form_designer', name='form_designer'),
    # url(r'^$', 'onadata.apps.main.views.configure_template'),
    url(r'^configure_template/$', 'onadata.apps.main.views.configure_template', name='configure_template'),
    url(r'^tutorial/$', 'onadata.apps.main.views.tutorial', name='tutorial'),
    url(r'^about-us/$', 'onadata.apps.main.views.about_us', name='about-us'),
    url(r'^getting_started/$', 'onadata.apps.main.views.getting_started',
        name='getting_started'),
    url(r'^faq/$', 'onadata.apps.main.views.faq', name='faq'),
    url(r'^syntax/$', 'onadata.apps.main.views.syntax', name='syntax'),
    url(r'^privacy/$', 'onadata.apps.main.views.privacy', name='privacy'),
    url(r'^tos/$', 'onadata.apps.main.views.tos', name='tos'),
    url(r'^resources/$', 'onadata.apps.main.views.resources',
        name='resources'),
    url(r'^forms/$', 'onadata.apps.main.views.form_gallery',
        name='forms_list'),
    url(r'^forms/(?P<uuid>[^/]+)$', 'onadata.apps.main.views.show'),
    url(r'^people/$', 'onadata.apps.main.views.members_list'),
    url(r'^xls2xform/$', 'onadata.apps.main.views.xls2xform'),
    url(r'^support/$', 'onadata.apps.main.views.support'),
    url(r'^stats/$', 'onadata.apps.stats.views.stats', name='form-stats'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/stats$',
        'onadata.apps.viewer.views.charts', name='form-stats'),
    url(r'^login_redirect/$', 'onadata.apps.main.views.login_redirect'),
    url(r"^attachment/$", 'onadata.apps.viewer.views.attachment_url'),
    url(r"^attachment/(?P<size>[^/]+)$",
        'onadata.apps.viewer.views.attachment_url'),
    url(r'^jsi18n/$', 'django.views.i18n.javascript_catalog',
        {'packages': ('main', 'viewer',)}),
    url(r'^typeahead_usernames', 'onadata.apps.main.views.username_list',
        name='username_list'),
    url(r'^(?P<username>[^/]+)/$',
        'onadata.apps.main.views.profile', name='user_profile'),

    url(r'^(?P<username>[^/]+)/uiformbuilder/add-form-json/$',
        'onadata.apps.main.views.uiformbuilder_add_form_json', name='uiformbuilder_add_form_json'),
    url(r'^(?P<username>[^/]+)/uiformbuilder/list-form-json/$',
        'onadata.apps.main.views.uiformbuilder_list_form_json', name='uiformbuilder_list_form_json'),
    url(r'^(?P<username>[^/]+)/uiformbuilder/update-form-json/$',
        'onadata.apps.main.views.uiformbuilder_update_form_json', name='uiformbuilder_update_form_json'),
    url(r'^(?P<username>[^/]+)/uiformbuilder/publish-form-json/$',
        'onadata.apps.main.views.uiformbuilder_publish_form_json', name='uiformbuilder_publish_form_json'),


    url(r'^(?P<username>[^/]+)/form_publish/$',
        'onadata.apps.main.views.form_publish', name='form_publish'),
    url(r'^(?P<username>[^/]+)/form_publish_from_ui/$',
        'onadata.apps.main.views.form_publish_from_ui', name='form_publish_from_ui'),
    url(r'^(?P<username>[^/]+)/form_replace_from_ui/(?P<id_string>[^/]+)/$',
        'onadata.apps.main.views.form_replace_from_ui', name='form_replace_from_ui'),
    url(r'^(?P<username>[^/]+)/profile$',
        'onadata.apps.main.views.public_profile',
        name='public_profile'),
    url(r'^(?P<username>[^/]+)/settings',
        'onadata.apps.main.views.profile_settings'),
    url(r'^(?P<username>[^/]+)/cloneform$',
        'onadata.apps.main.views.clone_xlsform'),
    url(r'^(?P<username>[^/]+)/activity$',
        'onadata.apps.main.views.activity'),
    url(r'^(?P<username>[^/]+)/activity/api$',
        'onadata.apps.main.views.activity_api'),
    url(r'^activity/fields$', 'onadata.apps.main.views.activity_fields'),
    url(r'^(?P<username>[^/]+)/api-token$',
        'onadata.apps.main.views.api_token'),
    url(r"^(?P<username>\w+)/login",
        XFormListApi.as_view({'get': 'mobile_login'}), name='mobile_login'),
    url(r"^(?P<username>\w+)/m/formList$",
        'onadata.apps.logger.views.formList'),

    # MPOWER added
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data-inst-view",
        'onadata.apps.viewer.views.custom_data_view'),

    # form specific
    url(r'^(?P<username>[^/]+)/form_replace/(?P<id_string>[^/]+)/$', 'onadata.apps.main.views.form_replace'),
    url(r'^(?P<username>[^/]+)/form_reload/(?P<id_string>[^/]+)/$', 'onadata.apps.main.views.reload_xlsform'),
    # ############### Schedule ##############
    # url(r'^(?P<username>[^/]+)/form_schedule/(?P<id_string>[^/]+)/$', 'onadata.apps.main.views.form_schedule'),
    ############### Schedule ##############
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)$',
        'onadata.apps.main.views.show'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/qrcode$',
        'onadata.apps.main.views.qrcode', name='get_qrcode'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/api$',
        'onadata.apps.main.views.api', name='mongo_view_api'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/public_api$',
        'onadata.apps.main.views.public_api', name='public_api'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/delete_data$',
        'onadata.apps.main.views.delete_data', name='delete_data'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/edit$',
        'onadata.apps.main.views.edit'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/perms$',
        'onadata.apps.main.views.set_perm'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/bamboo$',
        'onadata.apps.main.views.link_to_bamboo'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/photos',
        'onadata.apps.main.views.form_photos'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/doc/(?P<data_id>\d+)'
        '', 'onadata.apps.main.views.download_metadata'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/delete-doc/(?P<data_'
        'id>\d+)', 'onadata.apps.main.views.delete_metadata'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/formid-media/(?P<dat'
        'a_id>\d+)', 'onadata.apps.main.views.download_media_data'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/addservice$',
        'onadata.apps.restservice.views.add_service', name="add_restservice"),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/delservice$',
        'onadata.apps.restservice.views.delete_service',
        name="delete_restservice"),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/update$',
        'onadata.apps.main.views.update_xform'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/preview$',
        'onadata.apps.main.views.enketo_preview'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/form_settings$',
        'onadata.apps.main.views.show_project_settings', name='show_project_settings'),

    # briefcase api urls
    url(r"^(?P<username>\w+)/view/submissionList$",
        BriefcaseApi.as_view({'get': 'list', 'head': 'list'}),
        name='view-submission-list'),
    url(r"^(?P<username>\w+)/view/downloadSubmission$",
        BriefcaseApi.as_view({'get': 'retrieve', 'head': 'retrieve'}),
        name='view-download-submission'),
    url(r"^(?P<username>\w+)/formUpload$",
        BriefcaseApi.as_view({'post': 'create', 'head': 'create'}),
        name='form-upload'),
    url(r"^(?P<username>\w+)/upload$",
        BriefcaseApi.as_view({'post': 'create', 'head': 'create'}),
        name='upload'),

    # stats
    url(r"^stats/submissions/$", 'onadata.apps.stats.views.submissions'),

    # exporting stuff
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.csv$",
        'onadata.apps.viewer.views.data_export', name='csv_export',
        kwargs={'export_type': 'csv'}),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.xls",
        'onadata.apps.viewer.views.data_export', name='xls_export',
        kwargs={'export_type': 'xls'}),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.csv.zip",
        'onadata.apps.viewer.views.data_export', name='csv_zip_export',
        kwargs={'export_type': 'csv_zip'}),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.sav.zip",
        'onadata.apps.viewer.views.data_export', name='sav_zip_export',
        kwargs={'export_type': 'sav_zip'}),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.kml$",
        'onadata.apps.viewer.views.kml_export'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/data\.zip",
        'onadata.apps.viewer.views.zip_export'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/gdocs$",
        'onadata.apps.viewer.views.google_xls_export'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/map_embed",
        'onadata.apps.viewer.views.map_embed_view'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/map",
        'onadata.apps.viewer.views.map_view'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/instance",
        'onadata.apps.viewer.views.instance'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/enter-data",
        'onadata.apps.logger.views.enter_data', name='enter_data'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/add-submission-with",
        'onadata.apps.viewer.views.add_submission_with',
        name='add_submission_with'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/thank_you_submission",
        'onadata.apps.viewer.views.thank_you_submission',
        name='thank_you_submission'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/edit-data/(?P<data_id>"
        "\d+)$", 'onadata.apps.logger.views.edit_data', name='edit_data'),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/view-data",
        'onadata.apps.viewer.views.data_view'),

    url(r"^(?P<username>\w+)/exports/(?P<id_string>[^/]+)/(?P<export_type>\w+)"
        "/new$", 'onadata.apps.viewer.views.create_export'),
    url(r"^(?P<username>\w+)/exports/(?P<id_string>[^/]+)/(?P<export_type>\w+)"
        "/delete$", 'onadata.apps.viewer.views.delete_export'),
    url(r"^(?P<username>\w+)/exports/(?P<id_string>[^/]+)/(?P<export_type>\w+)"
        "/progress$", 'onadata.apps.viewer.views.export_progress'),
    url(r"^(?P<username>\w+)/exports/(?P<id_string>[^/]+)/(?P<export_type>\w+)"
        "/$", 'onadata.apps.viewer.views.export_list'),
    url(r"^(?P<username>\w+)/exports/(?P<id_string>[^/]+)/(?P<export_type>\w+)"
        "/(?P<filename>[^/]+)$",
        'onadata.apps.viewer.views.export_download'),
    url(r'^(?P<username>\w+)/forms/(?P<form_id_string>[^/]+)/spss_labels\.zip$',
        'onadata.apps.logger.views.download_spss_labels', name='download_spss_labels'),
    url(r'^(?P<username>\w+)/exports/', include('onadata.apps.export.urls')),

    url(r'^(?P<username>\w+)/reports/', include('onadata.apps.survey_report.urls')),

    # Formbuilder related API
    url(r"^(?P<username>\w+)/form_attributes$",
        XFormSubmissionApi.as_view({'post': 'get_form_attribute', 'options': 'send_option'}),
        name='form_attributes'),
    url(r"^(?P<username>\w+)/get_all_csv",
        XFormSubmissionApi.as_view({'get': 'get_all_csv', 'options': 'send_option'}),
        name='form_attributes'),
    url(r"^form_attributes/$",
        XFormSubmissionApi.as_view({'post': 'get_form_attribute', 'options': 'send_option'}),
        name='form_attributes'),
    # odk data urls
    url(r"^submission$",
        XFormSubmissionApi.as_view({'post': 'create', 'head': 'create'}),
        name='submissions'),
    url(r"^formList$",
        XFormListApi.as_view({'get': 'list'}), name='form-list'),
    url(r"^(?P<username>\w+)/formList$",
        XFormListApi.as_view({'get': 'list'}), name='form-list'),
    url(r"^(?P<username>\w+)/xformsManifest/(?P<pk>[\d+^/]+)$",
        XFormListApi.as_view({'get': 'manifest'}),
        name='manifest-url'),
    url(r"^xformsManifest/(?P<pk>[\d+^/]+)$",
        XFormListApi.as_view({'get': 'manifest'}),
        name='manifest-url'),
    url(r"^(?P<username>\w+)/xformsMedia/(?P<pk>[\d+^/]+)"
        "/(?P<metadata>[\d+^/.]+)$",
        XFormListApi.as_view({'get': 'media'}), name='xform-media'),
    url(r"^(?P<username>\w+)/xformsMedia/(?P<pk>[\d+^/]+)"
        "/(?P<metadata>[\d+^/.]+)\.(?P<format>[a-z0-9]+)$",
        XFormListApi.as_view({'get': 'media'}), name='xform-media'),
    url(r"^xformsMedia/(?P<pk>[\d+^/]+)/(?P<metadata>[\d+^/.]+)$",
        XFormListApi.as_view({'get': 'media'}), name='xform-media'),
    url(r"^xformsMedia/(?P<pk>[\d+^/]+)/(?P<metadata>[\d+^/.]+)\."
        "(?P<format>[a-z0-9]+)$",
        XFormListApi.as_view({'get': 'media'}), name='xform-media'),
    url(r"^(?P<username>\w+)/submission$",
        XFormSubmissionApi.as_view({'post': 'create', 'head': 'create'}),
        name='submissions'),
    url(r"^(?P<username>\w+)/bulk-submission$",
        'onadata.apps.logger.views.bulksubmission'),
    url(r"^(?P<username>\w+)/bulk-submission-form$",
        'onadata.apps.logger.views.bulksubmission_form'),
    url(r"^(?P<username>\w+)/forms/(?P<pk>[\d+^/]+)/form\.xml$",
        XFormListApi.as_view({'get': 'retrieve'}),
        name="download_xform"),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/form\.xml$",
        'onadata.apps.logger.views.download_xform', name="download_xform"),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/form\.xls$",
        'onadata.apps.logger.views.download_xlsform',
        name="download_xlsform"),
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/form\.json",
        'onadata.apps.logger.views.download_jsonform',
        name="download_jsonform"),
    url(r"^(?P<username>\w+)/delete/(?P<id_string>[^/]+)/$",
        'onadata.apps.logger.views.delete_xform'),
    url(r"^(?P<username>\w+)/(?P<id_string>[^/]+)/toggle_downloadable/$",
        'onadata.apps.logger.views.toggle_downloadable'),

    # SMS support
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/sms_submission/(?P<s'
        'ervice>[a-z]+)/?$',
        'onadata.apps.sms_support.providers.import_submission_for_form',
        name='sms_submission_form_api'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/sms_submission$',
        'onadata.apps.sms_support.views.import_submission_for_form',
        name='sms_submission_form'),
    url(r"^(?P<username>[^/]+)/sms_submission/(?P<service>[a-z]+)/?$",
        'onadata.apps.sms_support.providers.import_submission',
        name='sms_submission_api'),
    url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/sms_multiple_submiss'
        'ions$',
        'onadata.apps.sms_support.views.import_multiple_submissions_for_form',
        name='sms_submissions_form'),
    url(r"^(?P<username>[^/]+)/sms_multiple_submissions$",
        'onadata.apps.sms_support.views.import_multiple_submissions',
        name='sms_submissions'),
    url(r"^(?P<username>[^/]+)/sms_submission$",
        'onadata.apps.sms_support.views.import_submission',
        name='sms_submission'),

    # Stats tables
    url(r"^(?P<username>\w+)/forms/(?P<id_string>[^/]+)/tables",
        'onadata.apps.viewer.views.stats_tables'),

    # Ziggy
    url(r"^(?P<username>[^/]+)/form-submissions$",
        'onadata.apps.logger.views.ziggy_submissions'),

    # static media
    url(r'^media/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root': settings.MEDIA_ROOT}),
    url(r'^favicon\.ico',
        RedirectView.as_view(url='/static/images/favicon.ico')),

    # Statistics for superusers. The username is irrelevant, but leave it as
    # the first part of the path to avoid collisions
    url(r"^(?P<username>[^/]+)/superuser_stats/$",
        'onadata.apps.logger.views.superuser_stats'),
    url(r"^(?P<username>[^/]+)/superuser_stats/(?P<base_filename>[^/]+)$",
        'onadata.apps.logger.views.retrieve_superuser_stats'),
        
    # django debug toolbar
    url(r'^__debug__/', include(debug_toolbar.urls)),
)

urlpatterns += patterns('django.contrib.staticfiles.views',
                        url(r'^static/(?P<path>.*)$', 'serve'))
