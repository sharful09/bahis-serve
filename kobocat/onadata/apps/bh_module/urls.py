from django.conf.urls import patterns, url
from onadata.apps.bh_module import views, views_forms

urlpatterns = patterns('',
                       url(r'^add-module/$', views.add_module, name='add_module'),
                       url(r'^add-module/(?P<parent_id>\d+)/$$', views.add_module, name='add_module'),
                       url(r'^edit-module/(?P<module_id>\d+)/$',
                           views.edit_module, name='edit_module'),
                       url(r'^project-list/$', views.project_list,
                           name='project_list'),
                       url(r'^project-add/$', views.project_add,
                           name='project_add'),
                       url(r'^project-edit/(?P<project_id>\d+)/$', views.project_edit,
                           name='project_edit'),
                       url(r'^project-settings/$', views.project_settings,
                           name='project_settings'),
                       url(r'^project-profile/(?P<project_id>\d+)/$', views.project_profile,
                           name='project_profile'),
                       url(r'^module-list/$', views.module_list,
                           name='module_list'),
                       url(r'^module-profile/(?P<module_id>\d+)/$', views.module_profile,
                           name='module_profile'),
                       url(r'^module-list-config/(?P<module_id>\d+)/$',
                           views.module_list_config, name='index'),
                       url(r'^module-entry-config/(?P<module_id>\d+)/$',
                           views.module_entry_config, name='index'),
                       url(r'^module-container-config/(?P<module_id>\d+)/$',
                           views.module_container_config, name='index'),
                       url(r'^add/module-list-config/(?P<module_id>\d+)/$',
                           views.add_module_list, name='add_module_list'),
                       url(r'^module-properties/(?P<module_id>\d+)/$',
                           views.update_module_properties, name='module_properties'),
                       url(r'^get-column-name/$', views.get_column_details,
                           name="get_column_details"),
                       url(r'^get-datasource-query/(?P<datasource_id>\d+)/$',
                           views.get_datasource_query, name="get_datasource_query"),
                       url(r'^create-datasource/$', views.create_datasource,
                           name="create_datasource"),
                       url(r'^add-datasource/$', views.add_datasource,
                           name="add_datasource"),
                       url(r'^edit-datasource/(?P<datasource_id>\d+)/$',
                           views.edit_datasource, name="edit_datasource"),
                       url(r'^datasource-list/$', views.datasource_list,
                           name="datasource_list"),
                       url(r'^(?P<username>[^/]+)/forms/(?P<id_string>[^/]+)/form_settings/$',
                           views_forms.form_settings, name='form_settings'),
                       url(r'^edit/form-csv-config/(?P<xform_id>\d+)/$',
                           views_forms.update_form_csv, name='update_form_csv'),
                       url(r'^form-csv-config-list/(?P<xform_id>\d+)/$',
                           views_forms.form_csv_config_list, name='form_csv_config_list'),
                       url(r'^datasource-preview/(?P<datasource_id>\d+)$',
                           views.datasource_preview, name='datasource_preview'),
                       url(r'^datasource-view/(?P<datasource_id>\d+)/$',
                           views.datasource_view, name='datasource_view'),
                       url(r'^add/entry-settings/(?P<module_id>\d+)/$',
                           views.add_entry_config, name='add_entry_config'),
                       url(r'^get-form-column/(?P<xform_id>\d+)/$',
                           views.get_form_column, name="get_form_column"),
                       url(r'^add/container-settings/(?P<module_id>\d+)/$',
                           views.add_container_config, name='add_container_config'),
                       # -----------------List -------------
                       url(r'^get/list-workflow/(?P<list_id>\d+)/$',
                           views.get_list_workflow, name='get_list_workflow'),
                       url(r'^delete/list-workflow/(?P<workflow_id>\d+)/$',
                           views.delete_list_workflow, name='delete_list_workflow'),
                       url(r'^add/list-workflow/(?P<list_id>\d+)/$',
                           views.add_list_workflow, name='add_list_workflow'),
                       url(r'^list-view/generate/(?P<list_id>\d+)/$',
                           views.module_list_generate, name='module_list_generate'),
                       url(r'^list-view/get-data/(?P<list_id>\d+)/$',
                           views.filtered_data, name='filtered_data'),
                       # ------- List -------------------
                       url(r'^save-lookup-info/(?P<list_id>\d+)/$',
                           views.save_lookup_info, name='save_lookup_info'),
                       url(r'^fetch-lookup-info/(?P<list_id>\d+)/$',
                           views.fetch_lookup_info, name='fetch_lookup_info'),
                       url(r'^fetch-lookup-select-fields/$',
                           views.fetch_lookup_select_fields, name='fetch_lookup_select_fields'),
                       url(r'^add/lookup-column/(?P<list_id>\d+)/$',
                           views.add_lookup_column, name='add_lookup_column'),
                       url(r'^forms/data-embed/(?P<xform_id>\d+)/$',
                           views_forms.add_form_data_embed, name='add_form_data_embed'),
                       url(r'^module-access/(?P<module_id>\d+)/$',
                           views.module_access, name='module_access'),
                       url(r'^module/catchment-tree/(?P<module_id>\d+)/$',
                           views.module_catchment_tree, name='module_catchment_tree'),
                       url(r'^module_catchment_data_insert/$',
                           views.module_catchment_data_insert, name='module_catchment_data_insert'),

                       # ------------------- Master Data ---------------

                       url(r'^master-data-category/list/$',
                           views.category_list, name='category_list'),
                       url(r'^master-data-category/add/$',
                           views.category_add, name='category_add'),
                       url(r'^master-data-category/edit/(?P<category_id>\d+)/$',
                           views.category_edit, name='category_edit'),
                       url(r'^master-data-category/delete/(?P<category_id>\d+)/$',
                           views.category_delete, name='category_delete'),
                       url(r'^master-data-category/view/(?P<category_id>\d+)/$',
                           views.category_item_list, name='category_item_list'),
                       url(r'^master-data-category-item/add/(?P<category_id>\d+)/$',
                           views.category_item_add, name='category_item_add'),
                       url(r'^master-data-category-item/edit/(?P<category_id>\d+)/(?P<item_id>\d+)/$',
                           views.category_item_edit, name='category_item_edit'),
                        url(r'^master-data-category-item/delete/(?P<category_id>\d+)/(?P<item_id>\d+)/$',
                           views.category_item_delete, name='category_item_delete'),
                       # API
                       url(r'^(?P<username>[^/]+)/get/form-config/(?P<last_sync_time>\d+)/$',
                           views_forms.get_form_api, name="form-config"),
                       url(r'^(?P<username>[^/]+)/get-api/module-list/$',
                           views_forms.get_module_api, name="module-list"),
                       url(r'^(?P<username>[^/]+)/get-api/form-list/$',
                           views_forms.get_form_list_api, name="form-list"),
                       url(r'^(?P<username>[^/]+)/get-api/form-choices/$',
                           views_forms.get_form_choices_api, name="form-choices"),
                       url(r'^(?P<username>[^/]+)/get-api/list-def/$',
                           views_forms.get_list_def_api, name="list-def"),
                       url(r'^(?P<username>[^/]+)/submission/$',
                           views_forms.submission_request, name="submission_request"),
                       url(r'^form/(?P<username>[^/]+)/data-sync/$',
                           views_forms.data_sync, name="data_sync"),
                       url(r'^form/(?P<username>[^/]+)/data-sync-count/$',
                           views_forms.data_sync_count, name="data_sync_count"),
                       url(r'^form/(?P<username>[^/]+)/data-sync-paginated/$',
                           views_forms.data_sync_paginated, name="data_sync_paginated"),
                       url(r'^app-user-verify/$', views_forms.app_user_verify,
                           name="app_user_verify"),
                       url(r'^catchment-data-sync/$', views_forms.catchment_area_api,
                           name="catchment_area_api"),
                       url(r'^get-datasource-csv/(?P<form_id>\d+)/$', views_forms.get_datasource_csv),
                       url(r'^delete-datasource/$', views.delete_datasource),
                       # url(r'^master-data-sync/(?P<user_id>\d+)/$', views_forms.master_data_sync,
                       #     name="master_data_sync"),
                       url(r'^system-data-sync/(?P<username>[^/]+)/$', views_forms.system_tabl_sync,
                           name="system_tabl_sync"),
                       url(r'^get/query-result/$',
                           views_forms.get_qry_result, name="form-config"),

                       )
