from datetime import datetime
from django.contrib.contenttypes.models import ContentType
from django.views.decorators.csrf import csrf_exempt
import os
import json
import time
from bson import json_util

from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.files.storage import default_storage
from django.core.files.storage import get_storage_class
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import IntegrityError
from rest_framework.authtoken.models import Token
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseForbidden
from django.http import HttpResponseNotFound
from django.http import HttpResponseRedirect
from django.http import HttpResponseServerError
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.template import loader, RequestContext
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_http_methods
from guardian.shortcuts import assign_perm, remove_perm, get_users_with_perms

from onadata.apps.main.forms import UserProfileForm, FormLicenseForm, \
    DataLicenseForm, SupportDocForm, QuickConverterFile, QuickConverterURL, \
    QuickConverter, SourceForm, PermissionForm, MediaForm, MapboxLayerForm, \
    ActivateSMSSupportFom, ExternalExportForm
from onadata.apps.main.models import AuditLog, UserProfile, MetaData
from onadata.apps.logger.models import Instance, XForm
from onadata.apps.logger.views import enter_data
from onadata.apps.viewer.models.data_dictionary import DataDictionary, \
    upload_to
from onadata.apps.viewer.models.parsed_instance import \
    DATETIME_FORMAT, ParsedInstance
from onadata.apps.viewer.views import attachment_url
from onadata.apps.sms_support.tools import check_form_sms_compatibility, \
    is_sms_related
from onadata.apps.sms_support.autodoc import get_autodoc_for
from onadata.apps.sms_support.providers import providers_doc
from onadata.libs.utils.bamboo import get_new_bamboo_dataset, \
    delete_bamboo_dataset, ensure_rest_service
from onadata.libs.utils.decorators import is_owner
from onadata.libs.utils.logger_tools import response_with_mimetype_and_name, \
    publish_form
from onadata.libs.utils.user_auth import add_cors_headers
from onadata.libs.utils.user_auth import check_and_set_user_and_form
from onadata.libs.utils.user_auth import check_and_set_user
from onadata.libs.utils.user_auth import get_xform_and_perms
from onadata.libs.utils.user_auth import has_permission
from onadata.libs.utils.user_auth import has_edit_permission
from onadata.libs.utils.user_auth import helper_auth_helper
from onadata.libs.utils.user_auth import set_profile_data
from onadata.libs.utils.log import audit_log, Actions
from onadata.libs.utils.qrcode import generate_qrcode
from onadata.libs.utils.viewer_tools import enketo_url
from onadata.libs.utils.export_tools import upload_template_for_external_export
import xml.etree.ElementTree as ET
from django.db import connection
# from onadata.libs.tasks import instance_parse
import pandas as pd
from onadata.apps.usermodule.models import UserModuleProfile, UserPasswordHistory, UserFailedLogin, Organizations
from onadata.libs.utils.logger_tools import check_form_permissions, get_xform_list

from django.forms.formsets import formset_factory
from onadata.apps.usermodule.forms import ProjectPermissionForm
from onadata.apps.usermodule.views_project import get_own_and_partner_orgs_usermodule_users, get_permissions
from collections import OrderedDict
from onadata.apps.formmodule.form_republish import get_form_xls
from django.core.files.storage import FileSystemStorage
import requests
import decimal

from onadata.apps.formmodule.form_tools import generate_or_update_flat_table, \
    generate_insert_query

from onadata.settings.common import KOBO_SERVER, WEB_SERVER, FORM_RENDERER_SERVER, KOBO_MODULE_URL
from rest_framework import status
from . import uiform_publish

field_list = ''


class OverwriteStorage(FileSystemStorage):

    def get_available_name(self, name):
        if self.exists(name):
            os.remove(os.path.join(settings.MEDIA_ROOT, name))
        return name


def home(request):
    if request.user.username:
        return HttpResponseRedirect(
            reverse(profile, kwargs={'username': request.user.username}))

    return render(request, 'home.html')


@login_required
def configure_template(request):
    return render(request, 'configure_template.html')


@login_required
def login_redirect(request):
    return HttpResponseRedirect(reverse(profile,
                                        kwargs={'username': request.user.username}))


@require_POST
@login_required
def clone_xlsform(request, username):
    """
    Copy a public/Shared form to a users list of forms.
    Eliminates the need to download Excel File and upload again.
    """
    to_username = request.user.username
    message = {'type': None, 'text': '....'}
    message_list = []

    def set_form():
        form_owner = request.POST.get('username')
        id_string = request.POST.get('id_string')
        xform = XForm.objects.get(user__username__iexact=form_owner,
                                  id_string__exact=id_string)
        if len(id_string) > 0 and id_string[0].isdigit():
            id_string = '_' + id_string
        path = xform.xls.name
        if default_storage.exists(path):
            xls_file = upload_to(None, '%s%s.xls' % (
                id_string, XForm.CLONED_SUFFIX), to_username)
            xls_data = default_storage.open(path)
            xls_file = default_storage.save(xls_file, xls_data)
            survey = DataDictionary.objects.create(
                user=request.user,
                xls=xls_file
            ).survey
            # log to cloner's account
            audit = {}
            audit_log(
                Actions.FORM_CLONED, request.user, request.user,
                _("Cloned form '%(id_string)s'.") %
                {
                    'id_string': survey.id_string,
                }, audit, request)
            clone_form_url = reverse(
                show, kwargs={
                    'username': to_username,
                    'id_string': xform.id_string + XForm.CLONED_SUFFIX})
            return {
                'type': 'alert-success',
                'text': _(u'Successfully cloned to %(form_url)s into your '
                          u'%(profile_url)s') %
                        {'form_url': u'<a href="%(url)s">%(id_string)s</a> ' % {
                            'id_string': survey.id_string,
                            'url': clone_form_url
                        },
                         'profile_url': u'<a href="%s">profile</a>.' %
                                        reverse(profile, kwargs={'username': to_username})}
            }

    form_result = publish_form(set_form)
    if form_result['type'] == 'alert-success':
        # comment the following condition (and else)
        # when we want to enable sms check for all.
        # until then, it checks if form barely related to sms
        if is_sms_related(form_result.get('form_o')):
            form_result_sms = check_form_sms_compatibility(form_result)
            message_list = [form_result, form_result_sms]
        else:
            message = form_result
    else:
        message = form_result

    context = RequestContext(request, {
        'message': message, 'message_list': message_list})

    if request.is_ajax():
        res = loader.render_to_string(
            'message.html',
            context_instance=context
        ).replace("'", r"\'").replace('\n', '')

        return HttpResponse(
            "$('#mfeedback').html('%s').show();" % res)
    else:
        return HttpResponse(message['text'])


# @require_POST
@login_required
def reload_xlsform(request, username, id_string):
    """
    Copy a public/Shared form to a users list of forms.
    Eliminates the need to download Excel File and upload again.
    """
    to_username = request.user.username
    message = {'type': None, 'text': '....'}
    message_list = []
    data = {}
    data["id_string"] = id_string
    data["username"] = to_username

    if request.method == 'POST' and request.user.is_authenticated():

        def set_form():
            form_owner = request.POST.get('username')
            id_string = request.POST.get('form_id_string')
            xform = XForm.objects.get(user__username__iexact=form_owner,
                                      id_string__exact=id_string)
            if len(id_string) > 0 and id_string[0].isdigit():
                id_string = '_' + id_string
            path = xform.xls.name
            if default_storage.exists(path):
                ts = time.time()
                ts = str(int(ts))

                f = (os.path.basename(path))
                ext = os.path.splitext(f)[1]
                print(ext)

                xls_file = 'parsed_forms/%s%s.%s' % (id_string, ts, ext)
                print(default_storage.location)

                xls_file = os.path.join(default_storage.location, 'parsed_forms', '%s%s%s' % (id_string, ts, ext))

                get_form_xls(os.path.join(default_storage.location, path), xls_file)
                print(default_storage.exists(xls_file))
                # return render(request, "form_reload.html", data)

                if default_storage.exists(xls_file):
                    xls_file = default_storage.open(xls_file)
                    print xls_file
                    if id_string:
                        survey = DataDictionary.objects.get(user=request.user, id_string=id_string)
                        survey.xls = xls_file
                        survey.save()

                        audit = {}
                        audit_log(
                            Actions.FORM_CLONED, request.user, request.user,
                            _("Master data reloaded '%(id_string)s'.") %
                            {
                                'id_string': xform.id_string,  # survey.id_string,
                            }, audit, request)
                        clone_form_url = reverse(
                            show, kwargs={
                                'username': to_username,
                                'id_string': xform.id_string})
                        return {
                            'type': 'alert-success',
                            'text': 'Successfully reloaded form',
                            'form_id_string': survey.id_string
                        }
                    else:
                        return {
                            'type': 'alert-error',
                            'text': 'No id_string'
                        }
                else:
                    return {
                        'type': 'alert-error',
                        'text': 'No id_string'
                    }

        form_result = publish_form(set_form)
        if form_result['type'] == 'alert-success':
            xform = get_object_or_404(XForm, user__username__iexact=username,
                                      id_string__exact=form_result['form_id_string'])
            root = ET.fromstring(xform.xml.encode('utf-8'))
            parseXML(root, 0, '', form_result['form_id_string'])

            global field_list

            cursor = connection.cursor()
            qry_parse = "select * from get_xform_extracted(" + str(xform.id) + ",'" + field_list + "')"
            # print qry_parse
            cursor.execute(qry_parse)
            cursor.close()

            generate_or_update_flat_table(xform.id)

            if is_sms_related(form_result.get('form_o')):
                form_result_sms = check_form_sms_compatibility(form_result)
                data['message_list'] = [form_result, form_result_sms]
            else:
                data['message'] = form_result
        else:
            data['message'] = form_result

        return render(request, "form_reload.html", data)

    return render(request, "form_reload.html", data)


def auto_reload_xlsform(request, username, id_string):
    """
    Copy a public/Shared form to a users list of forms.
    Eliminates the need to download Excel File and upload again.
    """
    to_username = request.user.username
    message = {'type': None, 'text': '....'}
    message_list = []
    data = {}
    data["id_string"] = id_string
    data["username"] = to_username

    if request.method == 'POST' and request.user.is_authenticated():

        def set_form():
            form_owner = request.POST.get('username')
            id_string = request.POST.get('form_id_string')
            xform = XForm.objects.get(user__username__iexact=form_owner,
                                      id_string__exact=id_string)
            if len(id_string) > 0 and id_string[0].isdigit():
                id_string = '_' + id_string
            path = xform.xls.name
            if default_storage.exists(path):
                ts = time.time()
                ts = str(int(ts))

                f = (os.path.basename(path))
                ext = os.path.splitext(f)[1]
                print(ext)

                xls_file = 'parsed_forms/%s%s.%s' % (id_string, ts, ext)
                print(default_storage.location)

                xls_file = os.path.join(default_storage.location, 'parsed_forms', '%s%s%s' % (id_string, ts, ext))

                get_form_xls(os.path.join(default_storage.location, path), xls_file)
                print(default_storage.exists(xls_file))
                # return render(request, "form_reload.html", data)

                if default_storage.exists(xls_file):
                    xls_file = default_storage.open(xls_file)
                    print xls_file
                    if id_string:
                        survey = DataDictionary.objects.get(user=request.user, id_string=id_string)
                        survey.xls = xls_file
                        survey.save()

                        audit = {}
                        audit_log(
                            Actions.FORM_CLONED, request.user, request.user,
                            _("Master data reloaded '%(id_string)s'.") %
                            {
                                'id_string': xform.id_string,  # survey.id_string,
                            }, audit, request)
                        clone_form_url = reverse(
                            show, kwargs={
                                'username': to_username,
                                'id_string': xform.id_string})
                        return {
                            'type': 'alert-success',
                            'text': 'Successfully reloaded form',
                            'form_id_string': survey.id_string
                        }
                    else:
                        return {
                            'type': 'alert-error',
                            'text': 'No id_string'
                        }
                else:
                    return {
                        'type': 'alert-error',
                        'text': 'No id_string'
                    }

        form_result = publish_form(set_form)
        if form_result['type'] == 'alert-success':
            xform = get_object_or_404(XForm, user__username__iexact=username,
                                      id_string__exact=form_result['form_id_string'])
            root = ET.fromstring(xform.xml.encode('utf-8'))
            parseXML(root, 0, '', form_result['form_id_string'])

            global field_list

            cursor = connection.cursor()
            qry_parse = "select * from get_xform_extracted(" + str(xform.id) + ",'" + field_list + "')"
            # print qry_parse
            cursor.execute(qry_parse)
            cursor.close()

            generate_or_update_flat_table(xform.id)

            if is_sms_related(form_result.get('form_o')):
                form_result_sms = check_form_sms_compatibility(form_result)
                data['message_list'] = [form_result, form_result_sms]
            else:
                data['message'] = form_result
        else:
            data['message'] = form_result

        # return render(request, "form_reload.html", data)

    # return render(request, "form_reload.html", data)


@csrf_exempt
def form_replace_from_ui(request,username,id_string):
    if request.method == 'POST':
        xform = get_object_or_404(XForm, user__username__iexact=username, id_string__exact=id_string)
        owner = xform.user
        user = User.objects.get(username=username)

        def set_form():
            form = QuickConverter(request.POST, request.FILES)

            survey = form.publish(user, id_string).survey

            enketo_webform_url = reverse(
                enter_data,
                kwargs={'username': username, 'id_string': survey.id_string}
            )
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_XLS_UPDATED, user, owner,
                _("XLS for '%(id_string)s' updated.") %
                {
                    'id_string': xform.id_string,
                }, audit, request)
            return {
                'type': 'alert-success',
                'text': _(u'Successfully published %(form_id)s.'
                          u' <a href="%(form_url)s">Enter Web Form</a>'
                          u' or <a href="#preview-modal" data-toggle="modal">'
                          u'Preview Web Form</a>')
                        % {'form_id': survey.id_string,
                           'form_url': enketo_webform_url}
            }

        message = publish_form(set_form)

        if message['type'] == 'alert-success':
            request.POST['username'] = username
            request.POST['form_id_string'] = id_string
            auto_reload_xlsform(request, username, id_string)
            xform = get_object_or_404(XForm, user__username__iexact=username, id_string__exact=id_string)
            # root = ET.fromstring(xform.xml)
            root = ET.fromstring(xform.xml.encode('utf-8'))
            # printRecur(root,0,'',form_result['form_id_string'])
            parseXML(root, 0, '', id_string)
            global field_list
            cursor = connection.cursor()
            qry_parse = "select * from get_xform_extracted(" + str(xform.id) + ",'" + field_list + "')"
            cursor.execute(qry_parse)
            cursor.close()

            generate_or_update_flat_table(xform.id)
            return HttpResponse(json.dumps({'msg':'Form replaced Successfully'}))
        else:
            return HttpResponse(json.dumps({'msg': 'Form replacement Failed'}))



@csrf_exempt
def form_publish_from_ui(request,username):
    user = User.objects.get(username=username)
    data = {}
    if request.method == 'POST':
        def set_form():
            form_owner = username  # request.POST.get('username')
            # id_string = request.POST.get('id_string')
            # xform = XForm.objects.get(user__username__iexact=form_owner,
            #                        id_string__exact=id_string)
            # if len(id_string) > 0 and id_string[0].isdigit():
            #    id_string = '_' + id_string
            # path = xform.xls.name
            form_file = request.FILES['xls_file']
            fs = FileSystemStorage()
            filename = fs.save(form_file.name, form_file)
            uploaded_file_path = fs.path(filename)
            get_form_xls(uploaded_file_path, 'onadata/media/parsed_forms/' + str(filename))
            # filename = "a_B35DGfJ.xlsx"

            path = 'parsed_forms/' + str(filename)
            print(default_storage.exists(path))
            print path
            if default_storage.exists(path):
                xls_file = default_storage.open(path)
                print(xls_file)
                survey = DataDictionary.objects.create(
                    user=user,
                    xls=xls_file
                ).survey
            return {
                'type': 'alert-success',
                'text': 'Successfully Uploaded',
                'form_id_string': survey.id_string
            }

        print("here")
        form_result = publish_form(set_form)
        print form_result
        if form_result['type'] == 'alert-success':
            xform = get_object_or_404(XForm, user__username__iexact=username,
                                      id_string__exact=form_result['form_id_string'])
            root = ET.fromstring(xform.xml.encode('utf-8'))
            parseXML(root, 0, '', form_result['form_id_string'])

            global field_list

            cursor = connection.cursor()
            qry_parse = "select * from get_xform_extracted(" + str(xform.id) + ",'" + field_list + "')"
            # print qry_parse
            cursor.execute(qry_parse)
            cursor.close()

            generate_or_update_flat_table(xform.id)

            if is_sms_related(form_result.get('form_o')):
                form_result_sms = check_form_sms_compatibility(form_result)
                data['message_list'] = [form_result, form_result_sms]
            else:
                data['message'] = form_result
            return HttpResponse(json.dumps(data))
        else:
            return HttpResponse(json.dumps(form_result))


def form_publish(request, username):
    print "test profile __________________________________________________"
    content_user = get_object_or_404(User, username__iexact=username)
    # form = QuickConverter()
    data = {}
    if request.method == 'POST' and request.user.is_authenticated():
        def set_form():
            form_owner = username  # request.POST.get('username')
            # id_string = request.POST.get('id_string')
            # xform = XForm.objects.get(user__username__iexact=form_owner,
            #                        id_string__exact=id_string)
            # if len(id_string) > 0 and id_string[0].isdigit():
            #    id_string = '_' + id_string
            # path = xform.xls.name
            form_file = request.FILES['xls_file']
            fs = FileSystemStorage()

            print('Form file is here:')
            print('Form file is here:')
            print('Form file is here:')
            print(form_file)
            print('Form file is here(name):')
            print(form_file.name)

            filename = fs.save(form_file.name, form_file)
            print('filename:')
            print(filename)
            uploaded_file_path = fs.path(filename)
            print('uploaded  file path is here:')
            print('uploaded  file path is here:')
            print('uploaded  file path is here:')
            print(uploaded_file_path)

            get_form_xls(uploaded_file_path, '/src_bahis/kobocat/onadata/media/parsed_forms/' + str(filename))
            # filename = "a_B35DGfJ.xlsx"

            path = 'parsed_forms/' + str(filename)
            print(default_storage.exists(path))
            print path
            if default_storage.exists(path):
                xls_file = default_storage.open(path)
                print(xls_file)
                survey = DataDictionary.objects.create(
                    user=request.user,
                    xls=xls_file
                ).survey
            return {
                'type': 'alert-success',
                'text': 'Successfully Uploaded',
                'form_id_string': survey.id_string
            }

        print("here")
        form_result = publish_form(set_form)
        print form_result
        if form_result['type'] == 'alert-success':
            xform = get_object_or_404(XForm, user__username__iexact=username,
                                      id_string__exact=form_result['form_id_string'])
            root = ET.fromstring(xform.xml.encode('utf-8'))
            parseXML(root, 0, '', form_result['form_id_string'])

            global field_list

            cursor = connection.cursor()
            qry_parse = "select * from get_xform_extracted(" + str(xform.id) + ",'" + field_list + "')"
            # print qry_parse
            cursor.execute(qry_parse)
            cursor.close()

            generate_or_update_flat_table(xform.id)

            if is_sms_related(form_result.get('form_o')):
                form_result_sms = check_form_sms_compatibility(form_result)
                data['message_list'] = [form_result, form_result_sms]
            else:
                data['message'] = form_result
        else:
            data['message'] = form_result

        return render(request, "test_profile.html", data)

    # xlsform submission...

    return render(request, "test_profile.html", data)


def profile(request, username):
    print "profile __________________________________________________"
    content_user = get_object_or_404(User, username__iexact=username)
    form = QuickConverter()
    data = {'form': form}

    # xlsform submission...
    if request.method == 'POST' and request.user.is_authenticated():
        def set_form():
            form = QuickConverter(request.POST, request.FILES)
            print "form upload error_________________________________________________"
            survey = form.publish(request.user).survey
            audit = {}
            audit_log(
                Actions.FORM_PUBLISHED, request.user, content_user,
                _("Published form '%(id_string)s'.") %
                {
                    'id_string': survey.id_string,
                }, audit, request)
            enketo_webform_url = reverse(
                enter_data,
                kwargs={'username': username, 'id_string': survey.id_string}
            )
            return {
                'type': 'alert-success',
                'form_id_string': survey.id_string,
                'preview_url': reverse(enketo_preview, kwargs={
                    'username': username,
                    'id_string': survey.id_string
                }),
                'text': _(u'Successfully published %(form_id)s.'
                          u' <a href="%(form_url)s">Enter Web Form</a>'
                          u' or <a href="#preview-modal" data-toggle="modal">'
                          u'Preview Web Form</a>')
                        % {'form_id': survey.id_string,
                           'form_url': enketo_webform_url},
                'form_o': survey
            }

        form_result = publish_form(set_form)
        if form_result['type'] == 'alert-success':
            request.POST['username'] = username
            request.POST['form_id_string'] = form_result['form_id_string']
            auto_reload_xlsform(request, username, form_result['form_id_string'])
            # comment the following condition (and else)
            # when we want to enable sms check for all.
            # until then, it checks if form barely related to sms
            xform = get_object_or_404(XForm, user__username__iexact=username,
                                      id_string__exact=form_result['form_id_string'])
            root = ET.fromstring(xform.xml.encode('utf-8'))
            parseXML(root, 0, '', form_result['form_id_string'])

            global field_list

            cursor = connection.cursor()
            qry_parse = "select * from get_xform_extracted(" + str(xform.id) + ",'" + field_list + "')"
            # print qry_parse
            cursor.execute(qry_parse)
            cursor.close()

            generate_or_update_flat_table(xform.id)

            if is_sms_related(form_result.get('form_o')):
                form_result_sms = check_form_sms_compatibility(form_result)
                data['message_list'] = [form_result, form_result_sms]
            else:
                data['message'] = form_result
        else:
            data['message'] = form_result

    # profile view...
    # for the same user -> dashboard
    '''
    if content_user == request.user:
        show_dashboard = True
        all_forms = content_user.xforms.count()
        form = QuickConverterFile()
        form_url = QuickConverterURL()

        request_url = request.build_absolute_uri(
            "/%s" % request.user.username)
        url = request_url.replace('http://', 'https://')
        xforms = XForm.objects.filter(user=content_user) \
            .select_related('user', 'instances')
        user_xforms = xforms
        # forms shared with user
        xfct = ContentType.objects.get(app_label='logger', model='xform')
        xfs = content_user.userobjectpermission_set.filter(content_type=xfct)
        shared_forms_pks = list(set([xf.object_pk for xf in xfs]))
        forms_shared_with = XForm.objects.filter(
            pk__in=shared_forms_pks).exclude(user=content_user) \
            .select_related('user')
        # all forms to which the user has access
        published_or_shared = XForm.objects.filter(
            pk__in=shared_forms_pks).select_related('user')
        xforms_list = [
            {
                'id': 'published',
                'xforms': user_xforms,
                'title': _(u"Published Forms"),
                'small': _("Export, map, and view submissions.")
            },
            {
                'id': 'shared',
                'xforms': forms_shared_with,
                'title': _(u"Shared Forms"),
                'small': _("List of forms shared with you.")
            },
            {
                'id': 'published_or_shared',
                'xforms': published_or_shared,
                'title': _(u"Published Forms"),
                'small': _("Export, map, and view submissions.")
            }
        ]
        data.update({
            'all_forms': all_forms,
            'show_dashboard': show_dashboard,
            'form': form,
            'form_url': form_url,
            'url': url,
            'user_xforms': user_xforms,
            'xforms_list': xforms_list,
            'forms_shared_with': forms_shared_with
        })
    '''
    # for any other user -> profile
    set_profile_data(data, content_user)
    print "profile end************************************************"
    return render(request, "profile.html", data)


def members_list(request):
    if not request.user.is_staff and not request.user.is_superuser:
        return HttpResponseForbidden(_(u'Forbidden.'))
    users = User.objects.all()
    template = 'people.html'

    return render(request, template, {'template': template, 'users': users})


@login_required
def profile_settings(request, username):
    content_user = check_and_set_user(request, username)
    profile, created = UserProfile.objects.get_or_create(user=content_user)
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            # get user
            # user.email = cleaned_email
            '''
            The email field has been removed from the profile form.
            form.instance.user.email = form.cleaned_data['email']
            form.instance.user.save()
            '''
            form.save()
            # todo: add string rep. of settings to see what changed
            audit = {}
            audit_log(
                Actions.PROFILE_SETTINGS_UPDATED, request.user, content_user,
                _("Profile settings updated."), audit, request)
            return HttpResponseRedirect(reverse(
                public_profile, kwargs={'username': request.user.username}
            ))
    else:
        form = UserProfileForm(
            instance=profile, initial={"email": content_user.email})

    return render(request, "settings.html",
                  {'content_user': content_user, 'form': form})


@require_GET
def public_profile(request, username):
    content_user = check_and_set_user(request, username)
    if isinstance(content_user, HttpResponseRedirect):
        return content_user
    data = {}
    set_profile_data(data, content_user)
    data['is_owner'] = request.user == content_user
    audit = {}
    audit_log(
        Actions.PUBLIC_PROFILE_ACCESSED, request.user, content_user,
        _("Public profile accessed."), audit, request)

    return render(request, "profile.html", data)


@login_required
def dashboard(request):
    content_user = request.user
    data = {
        'form': QuickConverter(),
        'content_user': content_user,
        'url': request.build_absolute_uri("/%s" % request.user.username)
    }
    set_profile_data(data, content_user)

    return render(request, "dashboard.html", data)


def redirect_to_public_link(request, uuid):
    xform = get_object_or_404(XForm, uuid=uuid)
    request.session['public_link'] = \
        xform.uuid if MetaData.public_link(xform) else False

    return HttpResponseRedirect(reverse(show, kwargs={
        'username': xform.user.username,
        'id_string': xform.id_string
    }))


def set_xform_owner_data(data, xform, request, username, id_string):
    data['sms_support_form'] = ActivateSMSSupportFom(
        initial={'enable_sms_support': xform.allows_sms,
                 'sms_id_string': xform.sms_id_string})
    if not xform.allows_sms:
        data['sms_compatible'] = check_form_sms_compatibility(
            None, json_survey=json.loads(xform.json))
    else:
        url_root = request.build_absolute_uri('/')[:-1]
        data['sms_providers_doc'] = providers_doc(
            url_root=url_root,
            username=username,
            id_string=id_string)
        data['url_root'] = url_root

    data['form_license_form'] = FormLicenseForm(
        initial={'value': data['form_license']})
    data['data_license_form'] = DataLicenseForm(
        initial={'value': data['data_license']})
    data['doc_form'] = SupportDocForm()
    data['source_form'] = SourceForm()
    data['media_form'] = MediaForm()
    data['mapbox_layer_form'] = MapboxLayerForm()
    data['external_export_form'] = ExternalExportForm()
    users_with_perms = []

    for perm in get_users_with_perms(xform, attach_perms=True).items():
        has_perm = []
        if 'change_xform' in perm[1]:
            has_perm.append(_(u"Can Edit"))
        if 'view_xform' in perm[1]:
            has_perm.append(_(u"Can View"))
        if 'report_xform' in perm[1]:
            has_perm.append(_(u"Can submit to"))
        if 'validate_xform' in perm[1]:
            has_perm.append(_(u"Can Validate"))
        users_with_perms.append((perm[0], u" | ".join(has_perm)))
    data['users_with_perms'] = users_with_perms
    data['permission_form'] = PermissionForm(username)


@require_GET
def show(request, username=None, id_string=None, uuid=None):
    if uuid:
        return redirect_to_public_link(request, uuid)

    xform, is_owner, can_edit, can_view = get_xform_and_perms(
        username, id_string, request)
    # no access
    if not (xform.shared or can_view or request.session.get('public_link')):
        return HttpResponseRedirect(reverse(home))

    data = {}
    data['cloned'] = len(
        XForm.objects.filter(user__username__iexact=request.user.username,
                             id_string__exact=id_string + XForm.CLONED_SUFFIX)
    ) > 0
    data['public_link'] = MetaData.public_link(xform)
    data['is_owner'] = is_owner
    data['can_edit'] = can_edit
    data['can_view'] = can_view or request.session.get('public_link')
    data['xform'] = xform
    data['content_user'] = xform.user
    data['base_url'] = "https://%s" % request.get_host()
    data['source'] = MetaData.source(xform)
    data['form_license'] = MetaData.form_license(xform).data_value
    data['data_license'] = MetaData.data_license(xform).data_value
    data['supporting_docs'] = MetaData.supporting_docs(xform)
    data['media_upload'] = MetaData.media_upload(xform)
    data['mapbox_layer'] = MetaData.mapbox_layer_upload(xform)
    data['external_export'] = MetaData.external_export(xform)

    if is_owner:
        set_xform_owner_data(data, xform, request, username, id_string)

    if xform.allows_sms:
        data['sms_support_doc'] = get_autodoc_for(xform)

    return render(request, "show.html", data)


# SETTINGS SCREEN FOR KPI, LOADED IN IFRAME
@require_GET
def show_form_settings(request, username=None, id_string=None, uuid=None):
    if uuid:
        return redirect_to_public_link(request, uuid)

    xform, is_owner, can_edit, can_view = get_xform_and_perms(
        username, id_string, request)
    # no access
    if not (xform.shared or can_view or request.session.get('public_link')):
        return HttpResponseRedirect(reverse(home))

    data = {}
    data['cloned'] = len(
        XForm.objects.filter(user__username__iexact=request.user.username,
                             id_string__exact=id_string + XForm.CLONED_SUFFIX)
    ) > 0
    data['public_link'] = MetaData.public_link(xform)
    data['is_owner'] = is_owner
    data['can_edit'] = can_edit
    data['can_view'] = can_view or request.session.get('public_link')
    data['xform'] = xform
    data['content_user'] = xform.user
    data['base_url'] = "https://%s" % request.get_host()
    data['source'] = MetaData.source(xform)
    data['form_license'] = MetaData.form_license(xform).data_value
    data['data_license'] = MetaData.data_license(xform).data_value
    data['supporting_docs'] = MetaData.supporting_docs(xform)
    data['media_upload'] = MetaData.media_upload(xform)
    data['mapbox_layer'] = MetaData.mapbox_layer_upload(xform)
    data['external_export'] = MetaData.external_export(xform)

    if is_owner:
        set_xform_owner_data(data, xform, request, username, id_string)

    if xform.allows_sms:
        data['sms_support_doc'] = get_autodoc_for(xform)

    return render(request, "show_form_settings.html", data)


def show_project_settings(request, username, id_string):
    xform, is_owner, can_edit, can_view = get_xform_and_perms(
        username, id_string, request)
    # no access
    if not (xform.shared or can_view or request.session.get('public_link')):
        return HttpResponseRedirect(reverse(home))

    data = {}
    data.update({
        'cloned': len(
            XForm.objects.filter(user__username__iexact=request.user.username,
                                 id_string__exact=id_string + XForm.CLONED_SUFFIX)
        ) > 0,
        'public_link': MetaData.public_link(xform),
        'is_owner': is_owner,
        'can_edit': can_edit,
        'can_view': can_view or request.session.get('public_link'),
        'xform': xform,
        'content_user': xform.user,
        'base_url': "https://%s" % request.get_host(),
        'source': MetaData.source(xform),
        'form_license': MetaData.form_license(xform).data_value,
        'data_license': MetaData.data_license(xform).data_value,
        'supporting_docs': MetaData.supporting_docs(xform),
        'media_upload': MetaData.media_upload(xform),
        'mapbox_layer': MetaData.mapbox_layer_upload(xform),
        'external_export': MetaData.external_export(xform),
    })

    if is_owner:
        set_xform_owner_data(data, xform, request, username, id_string)

    if xform.allows_sms:
        data.update({
            'sms_support_doc': get_autodoc_for(xform),
        })

    """
    Adjusts the view, edit and submit
    permission of a project/form to the
    usermodule users of currently logged in
    user's organization and its partner
    organization.
    N.B. When edit permission is assigned
    view permission is also assigned.
    """

    user_list = get_own_and_partner_orgs_usermodule_users(request)

    initial_list = get_permissions(user_list, xform)
    PermisssionFormSet = formset_factory(ProjectPermissionForm, max_num=len(user_list))
    permisssion_form_set = PermisssionFormSet(initial=initial_list)
    data.update({
        'permisssion_form_set': permisssion_form_set,
    })
    # print 'data##################'
    # print str(data)
    if request.method == 'POST':
        permisssion_form_set = PermisssionFormSet(data=request.POST)
        for idx, user_role_form in enumerate(permisssion_form_set):
            u_id = request.POST['form-' + str(idx) + '-user']
            mist = initial_list[idx]['perm_type']
            current_user = User.objects.get(pk=u_id)
            results = map(str, request.POST.getlist('perm-' + str(idx + 1)))
            for result in results:
                if result == 'view' and not current_user.has_perm('view_xform', xform):
                    assign_perm('view_xform', current_user, xform)
                elif result == 'report' and not current_user.has_perm('report_xform', xform):
                    assign_perm('report_xform', current_user, xform)
                elif result == 'edit' and not current_user.has_perm('change_xform', xform):
                    assign_perm('change_xform', current_user, xform)
                    if not current_user.has_perm('view_xform', xform):
                        assign_perm('view_xform', current_user, xform)

            deleter = list(set(['edit', 'view', 'report']) - set(results))
            for delete_item in deleter:
                if delete_item == 'view' and current_user.has_perm('view_xform', xform) and not current_user.has_perm(
                        'change_xform', xform):
                    remove_perm('view_xform', current_user, xform)
                elif delete_item == 'report' and current_user.has_perm('report_xform', xform):
                    remove_perm('report_xform', current_user, xform)
                elif delete_item == 'edit' and current_user.has_perm('change_xform', xform):
                    remove_perm('change_xform', current_user, xform)
            message = "Permissions Saved"
            initial_list = get_permissions(user_list, xform)
            permisssion_form_set = PermisssionFormSet(initial=initial_list)
            data.update({
                'message': message,
                'permisssion_form_set': permisssion_form_set,
            })

    return render(request, "project_settings.html", data)


@login_required
@require_GET
def api_token(request, username=None):
    if request.user.username == username:
        user = get_object_or_404(User, username=username)
        data = {}
        data['token_key'], created = Token.objects.get_or_create(user=user)

        return render(request, "api_token.html", data)

    return HttpResponseForbidden(_(u'Permission denied.'))


@require_http_methods(["GET", "OPTIONS"])
def api(request, username=None, id_string=None):
    """
    Returns all results as JSON.  If a parameter string is passed,
    it takes the 'query' parameter, converts this string to a dictionary, an
    that is then used as a MongoDB query string.

    NOTE: only a specific set of operators are allow, currently $or and $and.
    Please send a request if you'd like another operator to be enabled.

    NOTE: Your query must be valid JSON, double check it here,
    http://json.parser.online.fr/

    E.g. api?query='{"last_name": "Smith"}'
    """
    if request.method == "OPTIONS":
        response = HttpResponse()
        add_cors_headers(response)

        return response
    helper_auth_helper(request)
    helper_auth_helper(request)
    xform, owner = check_and_set_user_and_form(username, id_string, request)

    if not xform:
        return HttpResponseForbidden(_(u'Not shared.'))

    try:
        args = {
            'username': username,
            'id_string': id_string,
            'query': request.GET.get('query'),
            'fields': request.GET.get('fields'),
            'sort': request.GET.get('sort')
        }
        if 'start' in request.GET:
            args["start"] = int(request.GET.get('start'))
        if 'limit' in request.GET:
            args["limit"] = int(request.GET.get('limit'))
        if 'count' in request.GET:
            args["count"] = True if int(request.GET.get('count')) > 0 \
                else False
        cursor = ParsedInstance.query_mongo(**args)
    except ValueError as e:
        return HttpResponseBadRequest(e.__str__())

    records = list(record for record in cursor)
    response_text = json_util.dumps(records)

    if 'callback' in request.GET and request.GET.get('callback') != '':
        callback = request.GET.get('callback')
        response_text = ("%s(%s)" % (callback, response_text))

    response = HttpResponse(response_text, content_type='application/json')
    add_cors_headers(response)

    return response


@require_GET
def public_api(request, username, id_string):
    """
    Returns public information about the form as JSON
    """

    xform = get_object_or_404(XForm,
                              user__username__iexact=username,
                              id_string__exact=id_string)

    _DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
    exports = {'username': xform.user.username,
               'id_string': xform.id_string,
               'bamboo_dataset': xform.bamboo_dataset,
               'shared': xform.shared,
               'shared_data': xform.shared_data,
               'downloadable': xform.downloadable,
               'title': xform.title,
               'date_created': xform.date_created.strftime(_DATETIME_FORMAT),
               'date_modified': xform.date_modified.strftime(_DATETIME_FORMAT),
               'uuid': xform.uuid,
               }
    response_text = json.dumps(exports)

    return HttpResponse(response_text, content_type='application/json')


@login_required
def edit(request, username, id_string):
    xform = XForm.objects.get(user__username__iexact=username,
                              id_string__exact=id_string)
    owner = xform.user

    if username == request.user.username or \
            request.user.has_perm('logger.change_xform', xform):
        if request.POST.get('description'):
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_UPDATED, request.user, owner,
                _("Description for '%(id_string)s' updated from "
                  "'%(old_description)s' to '%(new_description)s'.") %
                {
                    'id_string': xform.id_string,
                    'old_description': xform.description,
                    'new_description': request.POST['description']
                }, audit, request)
            xform.description = request.POST['description']
        elif request.POST.get('title'):
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_UPDATED, request.user, owner,
                _("Title for '%(id_string)s' updated from "
                  "'%(old_title)s' to '%(new_title)s'.") %
                {
                    'id_string': xform.id_string,
                    'old_title': xform.title,
                    'new_title': request.POST.get('title')
                }, audit, request)
            xform.title = request.POST['title']
        elif request.POST.get('toggle_shared'):
            if request.POST['toggle_shared'] == 'data':
                audit = {
                    'xform': xform.id_string
                }
                audit_log(
                    Actions.FORM_UPDATED, request.user, owner,
                    _("Data sharing updated for '%(id_string)s' from "
                      "'%(old_shared)s' to '%(new_shared)s'.") %
                    {
                        'id_string': xform.id_string,
                        'old_shared': _("shared")
                        if xform.shared_data else _("not shared"),
                        'new_shared': _("shared")
                        if not xform.shared_data else _("not shared")
                    }, audit, request)
                xform.shared_data = not xform.shared_data
            elif request.POST['toggle_shared'] == 'form':
                audit = {
                    'xform': xform.id_string
                }
                audit_log(
                    Actions.FORM_UPDATED, request.user, owner,
                    _("Form sharing for '%(id_string)s' updated "
                      "from '%(old_shared)s' to '%(new_shared)s'.") %
                    {
                        'id_string': xform.id_string,
                        'old_shared': _("shared")
                        if xform.shared else _("not shared"),
                        'new_shared': _("shared")
                        if not xform.shared else _("not shared")
                    }, audit, request)
                xform.shared = not xform.shared
            elif request.POST['toggle_shared'] == 'active':
                audit = {
                    'xform': xform.id_string
                }
                audit_log(
                    Actions.FORM_UPDATED, request.user, owner,
                    _("Active status for '%(id_string)s' updated from "
                      "'%(old_shared)s' to '%(new_shared)s'.") %
                    {
                        'id_string': xform.id_string,
                        'old_shared': _("shared")
                        if xform.downloadable else _("not shared"),
                        'new_shared': _("shared")
                        if not xform.downloadable else _("not shared")
                    }, audit, request)
                xform.downloadable = not xform.downloadable
        elif request.POST.get('form-license'):
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_UPDATED, request.user, owner,
                _("Form License for '%(id_string)s' updated to "
                  "'%(form_license)s'.") %
                {
                    'id_string': xform.id_string,
                    'form_license': request.POST['form-license'],
                }, audit, request)
            MetaData.form_license(xform, request.POST['form-license'])
        elif request.POST.get('data-license'):
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_UPDATED, request.user, owner,
                _("Data license for '%(id_string)s' updated to "
                  "'%(data_license)s'.") %
                {
                    'id_string': xform.id_string,
                    'data_license': request.POST['data-license'],
                }, audit, request)
            MetaData.data_license(xform, request.POST['data-license'])
        elif request.POST.get('source') or request.FILES.get('source'):
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_UPDATED, request.user, owner,
                _("Source for '%(id_string)s' updated to '%(source)s'.") %
                {
                    'id_string': xform.id_string,
                    'source': request.POST.get('source'),
                }, audit, request)
            MetaData.source(xform, request.POST.get('source'),
                            request.FILES.get('source'))
        elif request.POST.get('enable_sms_support_trigger') is not None:
            sms_support_form = ActivateSMSSupportFom(request.POST)
            if sms_support_form.is_valid():
                audit = {
                    'xform': xform.id_string
                }
                enabled = \
                    sms_support_form.cleaned_data.get('enable_sms_support')
                if enabled:
                    audit_action = Actions.SMS_SUPPORT_ACTIVATED
                    audit_message = _(u"SMS Support Activated on")
                else:
                    audit_action = Actions.SMS_SUPPORT_DEACTIVATED
                    audit_message = _(u"SMS Support Deactivated on")
                audit_log(
                    audit_action, request.user, owner,
                    audit_message
                    % {'id_string': xform.id_string}, audit, request)
                # stored previous states to be able to rollback form status
                # in case we can't save.
                pe = xform.allows_sms
                pid = xform.sms_id_string
                xform.allows_sms = enabled
                xform.sms_id_string = \
                    sms_support_form.cleaned_data.get('sms_id_string')
                compat = check_form_sms_compatibility(None,
                                                      json.loads(xform.json))
                if compat['type'] == 'alert-error':
                    xform.allows_sms = False
                    xform.sms_id_string = pid
                try:
                    xform.save()
                except IntegrityError:
                    # unfortunately, there's no feedback mechanism here
                    xform.allows_sms = pe
                    xform.sms_id_string = pid

        elif request.POST.get('media_url'):
            uri = request.POST.get('media_url')
            MetaData.media_add_uri(xform, uri)
        elif request.FILES.get('media'):
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_UPDATED, request.user, owner,
                _("Media added to '%(id_string)s'.") %
                {
                    'id_string': xform.id_string
                }, audit, request)
            for aFile in request.FILES.getlist("media"):
                MetaData.media_upload(xform, aFile)
        elif request.POST.get('map_name'):
            mapbox_layer = MapboxLayerForm(request.POST)
            if mapbox_layer.is_valid():
                audit = {
                    'xform': xform.id_string
                }
                audit_log(
                    Actions.FORM_UPDATED, request.user, owner,
                    _("Map layer added to '%(id_string)s'.") %
                    {
                        'id_string': xform.id_string
                    }, audit, request)
                MetaData.mapbox_layer_upload(xform, mapbox_layer.cleaned_data)
        elif request.FILES.get('doc'):
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_UPDATED, request.user, owner,
                _("Supporting document added to '%(id_string)s'.") %
                {
                    'id_string': xform.id_string
                }, audit, request)
            MetaData.supporting_docs(xform, request.FILES.get('doc'))
        elif request.POST.get("template_token") \
                and request.POST.get("template_token"):
            template_name = request.POST.get("template_name")
            template_token = request.POST.get("template_token")
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_UPDATED, request.user, owner,
                _("External export added to '%(id_string)s'.") %
                {
                    'id_string': xform.id_string
                }, audit, request)
            merged = template_name + '|' + template_token
            MetaData.external_export(xform, merged)
        elif request.POST.get("external_url") \
                and request.FILES.get("xls_template"):
            template_upload_name = request.POST.get("template_upload_name")
            external_url = request.POST.get("external_url")
            xls_template = request.FILES.get("xls_template")

            result = upload_template_for_external_export(external_url,
                                                         xls_template)
            status_code = result.split('|')[0]
            token = result.split('|')[1]
            if status_code == '201':
                data_value = \
                    template_upload_name + '|' + external_url + '/xls/' + token
                MetaData.external_export(xform, data_value=data_value)

        xform.update()

        if request.is_ajax():
            return HttpResponse(_(u'Updated succeeded.'))
        else:
            if 'HTTP_REFERER' in request.META and request.META['HTTP_REFERER'].strip():
                return HttpResponseRedirect(request.META['HTTP_REFERER'])

            return HttpResponseRedirect(reverse(show, kwargs={
                'username': username,
                'id_string': id_string
            }))

    return HttpResponseForbidden(_(u'Update failed.'))


def getting_started(request):
    template = 'getting_started.html'

    return render(request, 'base.html', {'template': template})


def support(request):
    template = 'support.html'

    return render(request, 'base.html', {'template': template})


def faq(request):
    template = 'faq.html'

    return render(request, 'base.html', {'template': template})


def xls2xform(request):
    template = 'xls2xform.html'

    return render(request, 'base.html', {'template': template})


def tutorial(request):
    template = 'tutorial.html'
    username = request.user.username if request.user.username else \
        'your-user-name'
    url = request.build_absolute_uri("/%s" % username)

    return render(request, 'base.html', {'template': template, 'url': url})


def resources(request):
    if 'fr' in request.LANGUAGE_CODE.lower():
        deck_id = 'a351f6b0a3730130c98b12e3c5740641'
    else:
        deck_id = '1a33a070416b01307b8022000a1de118'

    return render(request, 'resources.html', {'deck_id': deck_id})


def about_us(request):
    a_flatpage = '/about-us/'
    username = request.user.username if request.user.username else \
        'your-user-name'
    url = request.build_absolute_uri("/%s" % username)

    return render(request, 'base.html', {'a_flatpage': a_flatpage, 'url': url})


def privacy(request):
    template = 'privacy.html'

    return render(request, 'base.html', {'template': template})


def tos(request):
    template = 'tos.html'

    return render(request, 'base.html', {'template': template})


def syntax(request):
    template = 'syntax.html'

    return render(request, 'base.html', {'template': template})


def form_gallery(request):
    """
    Return a list of urls for all the shared xls files. This could be
    made a lot prettier.
    """
    data = {}
    if request.user.is_authenticated():
        data['loggedin_user'] = request.user
    data['shared_forms'] = XForm.objects.filter(shared=True)
    # build list of shared forms with cloned suffix
    id_strings_with_cloned_suffix = [
        x.id_string + XForm.CLONED_SUFFIX for x in data['shared_forms']
    ]
    # build list of id_strings for forms this user has cloned
    data['cloned'] = [
        x.id_string.split(XForm.CLONED_SUFFIX)[0]
        for x in XForm.objects.filter(
            user__username__iexact=request.user.username,
            id_string__in=id_strings_with_cloned_suffix
        )
    ]

    return render(request, 'form_gallery.html', data)


def download_metadata(request, username, id_string, data_id):
    xform = get_object_or_404(XForm,
                              user__username__iexact=username,
                              id_string__exact=id_string)
    owner = xform.user
    if username == request.user.username or xform.shared:
        data = get_object_or_404(MetaData, pk=data_id)
        file_path = data.data_file.name
        filename, extension = os.path.splitext(file_path.split('/')[-1])
        extension = extension.strip('.')
        dfs = get_storage_class()()
        if dfs.exists(file_path):
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_UPDATED, request.user, owner,
                _("Document '%(filename)s' for '%(id_string)s' downloaded.") %
                {
                    'id_string': xform.id_string,
                    'filename': "%s.%s" % (filename, extension)
                }, audit, request)
            response = response_with_mimetype_and_name(
                data.data_file_type,
                filename, extension=extension, show_date=False,
                file_path=file_path)
            return response
        else:
            return HttpResponseNotFound()

    return HttpResponseForbidden(_(u'Permission denied.'))


@login_required()
def delete_metadata(request, username, id_string, data_id):
    xform = get_object_or_404(XForm,
                              user__username__iexact=username,
                              id_string__exact=id_string)
    owner = xform.user
    data = get_object_or_404(MetaData, pk=data_id)
    dfs = get_storage_class()()
    req_username = request.user.username
    if request.GET.get('del', False) and username == req_username:
        try:
            dfs.delete(data.data_file.name)
            data.delete()
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_UPDATED, request.user, owner,
                _("Document '%(filename)s' deleted from '%(id_string)s'.") %
                {
                    'id_string': xform.id_string,
                    'filename': os.path.basename(data.data_file.name)
                }, audit, request)
            return HttpResponseRedirect(reverse(show, kwargs={
                'username': username,
                'id_string': id_string
            }))
        except Exception:
            return HttpResponseServerError()
    elif (request.GET.get('map_name_del', False) or
          request.GET.get('external_del', False)) and username == req_username:
        data.delete()
        audit = {
            'xform': xform.id_string
        }
        audit_log(
            Actions.FORM_UPDATED, request.user, owner,
            _("Map layer deleted from '%(id_string)s'.") %
            {
                'id_string': xform.id_string,
            }, audit, request)
        return HttpResponseRedirect(reverse(show, kwargs={
            'username': username,
            'id_string': id_string
        }))

    return HttpResponseForbidden(_(u'Permission denied.'))


def download_media_data(request, username, id_string, data_id):
    xform = get_object_or_404(
        XForm, user__username__iexact=username,
        id_string__exact=id_string)
    owner = xform.user
    data = get_object_or_404(MetaData, id=data_id)
    dfs = get_storage_class()()
    if request.GET.get('del', False):
        if username == request.user.username:
            try:
                # ensure filename is not an empty string
                if data.data_file.name != '':
                    dfs.delete(data.data_file.name)

                data.delete()
                audit = {
                    'xform': xform.id_string
                }
                audit_log(
                    Actions.FORM_UPDATED, request.user, owner,
                    _("Media download '%(filename)s' deleted from "
                      "'%(id_string)s'.") %
                    {
                        'id_string': xform.id_string,
                        'filename': os.path.basename(data.data_file.name)
                    }, audit, request)
                if 'HTTP_REFERER' in request.META and request.META['HTTP_REFERER'].strip():
                    return HttpResponseRedirect(request.META['HTTP_REFERER'])

                return HttpResponseRedirect(reverse(show, kwargs={
                    'username': username,
                    'id_string': id_string
                }))
            except Exception as e:
                return HttpResponseServerError(e)
    else:
        if username:  # == request.user.username or xform.shared:
            if data.data_file.name == '' and data.data_value is not None:
                return HttpResponseRedirect(data.data_value)

            file_path = data.data_file.name
            filename, extension = os.path.splitext(file_path.split('/')[-1])
            extension = extension.strip('.')
            if dfs.exists(file_path):
                audit = {
                    'xform': xform.id_string
                }
                audit_log(
                    Actions.FORM_UPDATED, request.user, owner,
                    _("Media '%(filename)s' downloaded from "
                      "'%(id_string)s'.") %
                    {
                        'id_string': xform.id_string,
                        'filename': os.path.basename(file_path)
                    }, audit, request)
                response = response_with_mimetype_and_name(
                    data.data_file_type,
                    filename, extension=extension, show_date=False,
                    file_path=file_path)
                return response
            else:
                return HttpResponseNotFound()

    return HttpResponseForbidden(_(u'Permission denied.'))


def form_photos(request, username, id_string):
    xform, owner = check_and_set_user_and_form(username, id_string, request)

    if not xform:
        return HttpResponseForbidden(_(u'Not shared.'))

    data = {}
    data['form_view'] = True
    data['content_user'] = owner
    data['xform'] = xform
    image_urls = []

    for instance in xform.instances.all():
        for attachment in instance.attachments.all():
            # skip if not image e.g video or file
            if not attachment.mimetype.startswith('image'):
                continue

            data = {}

            for i in ['small', 'medium', 'large', 'original']:
                url = reverse(attachment_url, kwargs={'size': i})
                url = '%s?media_file=%s' % (url, attachment.media_file.name)
                data[i] = url

            image_urls.append(data)

    data['images'] = image_urls
    data['profilei'], created = UserProfile.objects.get_or_create(user=owner)

    return render(request, 'form_photos.html', data)


@require_POST
def set_perm(request, username, id_string):
    xform = get_object_or_404(XForm,
                              user__username__iexact=username,
                              id_string__exact=id_string)
    owner = xform.user
    if username != request.user.username \
            and not has_permission(xform, username, request):
        return HttpResponseForbidden(_(u'Permission denied.'))

    try:
        perm_type = request.POST['perm_type']
        for_user = request.POST['for_user']
    except KeyError:
        return HttpResponseBadRequest()

    if perm_type in ['edit', 'view', 'report', 'validate', 'remove']:
        try:
            user = User.objects.get(username=for_user)
        except User.DoesNotExist:
            messages.add_message(
                request, messages.INFO,
                _(u"Wrong username <b>%s</b>." % for_user),
                extra_tags='alert-error')
        else:
            if perm_type == 'edit' and \
                    not user.has_perm('change_xform', xform):
                audit = {
                    'xform': xform.id_string
                }
                audit_log(
                    Actions.FORM_PERMISSIONS_UPDATED, request.user, owner,
                    _("Edit permissions on '%(id_string)s' assigned to "
                      "'%(for_user)s'.") %
                    {
                        'id_string': xform.id_string,
                        'for_user': for_user
                    }, audit, request)
                assign_perm('change_xform', user, xform)
            elif perm_type == 'view' and \
                    not user.has_perm('view_xform', xform):
                audit = {
                    'xform': xform.id_string
                }
                audit_log(
                    Actions.FORM_PERMISSIONS_UPDATED, request.user, owner,
                    _("View permissions on '%(id_string)s' "
                      "assigned to '%(for_user)s'.") %
                    {
                        'id_string': xform.id_string,
                        'for_user': for_user
                    }, audit, request)
                assign_perm('view_xform', user, xform)
            elif perm_type == 'report' and \
                    not user.has_perm('report_xform', xform):
                audit = {
                    'xform': xform.id_string
                }
                audit_log(
                    Actions.FORM_PERMISSIONS_UPDATED, request.user, owner,
                    _("Report permissions on '%(id_string)s' "
                      "assigned to '%(for_user)s'.") %
                    {
                        'id_string': xform.id_string,
                        'for_user': for_user
                    }, audit, request)
                assign_perm('report_xform', user, xform)
            elif perm_type == 'validate' and \
                    not user.has_perm('validate_xform', xform):
                audit = {
                    'xform': xform.id_string
                }
                audit_log(
                    Actions.FORM_PERMISSIONS_UPDATED, request.user, owner,
                    _("Validate permissions on '%(id_string)s' assigned to "
                      "'%(for_user)s'.") %
                    {
                        'id_string': xform.id_string,
                        'for_user': for_user
                    }, audit, request)
                assign_perm('validate_xform', user, xform)
            elif perm_type == 'remove':
                audit = {
                    'xform': xform.id_string
                }
                audit_log(
                    Actions.FORM_PERMISSIONS_UPDATED, request.user, owner,
                    _("All permissions on '%(id_string)s' "
                      "removed from '%(for_user)s'.") %
                    {
                        'id_string': xform.id_string,
                        'for_user': for_user
                    }, audit, request)
                remove_perm('change_xform', user, xform)
                remove_perm('view_xform', user, xform)
                remove_perm('report_xform', user, xform)
                remove_perm('validate_xform', user, xform)
    elif perm_type == 'link':
        current = MetaData.public_link(xform)
        if for_user == 'all':
            MetaData.public_link(xform, True)
        elif for_user == 'none':
            MetaData.public_link(xform, False)
        elif for_user == 'toggle':
            MetaData.public_link(xform, not current)
        audit = {
            'xform': xform.id_string
        }
        audit_log(
            Actions.FORM_PERMISSIONS_UPDATED, request.user, owner,
            _("Public link on '%(id_string)s' %(action)s.") %
            {
                'id_string': xform.id_string,
                'action': "created"
                if for_user == "all" or
                   (for_user == "toggle" and not current) else "removed"
            }, audit, request)

    if request.is_ajax():
        return HttpResponse(
            json.dumps(
                {'status': 'success'}), content_type='application/json')
    if 'HTTP_REFERER' in request.META and request.META['HTTP_REFERER'].strip():
        return HttpResponseRedirect(request.META['HTTP_REFERER'])

    return HttpResponseRedirect(reverse(show, kwargs={
        'username': username,
        'id_string': id_string
    }))


@require_POST
@login_required
def delete_data(request, username=None, id_string=None):
    xform, owner = check_and_set_user_and_form(username, id_string, request)
    response_text = u''
    if not xform or not has_edit_permission(
            xform, owner, request, xform.shared
    ):
        return HttpResponseForbidden(_(u'Not shared.'))

    data_id = request.POST.get('id')
    if not data_id:
        return HttpResponseBadRequest(_(u"id must be specified"))

    Instance.set_deleted_at(data_id)
    audit = {
        'xform': xform.id_string
    }
    audit_log(
        Actions.SUBMISSION_DELETED, request.user, owner,
        _("Deleted submission with id '%(record_id)s' "
          "on '%(id_string)s'.") %
        {
            'id_string': xform.id_string,
            'record_id': data_id
        }, audit, request)
    response_text = json.dumps({"success": "Deleted data %s" % data_id})
    if 'callback' in request.GET and request.GET.get('callback') != '':
        callback = request.GET.get('callback')
        response_text = ("%s(%s)" % (callback, response_text))

    return HttpResponse(response_text, content_type='application/json')


@require_POST
@is_owner
def link_to_bamboo(request, username, id_string):
    xform = get_object_or_404(XForm,
                              user__username__iexact=username,
                              id_string__exact=id_string)
    owner = xform.user
    audit = {
        'xform': xform.id_string
    }

    # try to delete the dataset first (in case it exists)
    if xform.bamboo_dataset and delete_bamboo_dataset(xform):
        xform.bamboo_dataset = u''
        xform.save()
        audit_log(
            Actions.BAMBOO_LINK_DELETED, request.user, owner,
            _("Bamboo link deleted on '%(id_string)s'.")
            % {'id_string': xform.id_string}, audit, request)

    # create a new one from all the data
    dataset_id = get_new_bamboo_dataset(xform)

    # update XForm
    xform.bamboo_dataset = dataset_id
    xform.save()
    ensure_rest_service(xform)

    audit_log(
        Actions.BAMBOO_LINK_CREATED, request.user, owner,
        _("Bamboo link created on '%(id_string)s'.") %
        {
            'id_string': xform.id_string,
        }, audit, request)

    return HttpResponseRedirect(reverse(show, kwargs={
        'username': username,
        'id_string': id_string
    }))


@require_POST
@is_owner
def update_xform(request, username, id_string):
    xform = get_object_or_404(
        XForm, user__username__iexact=username, id_string__exact=id_string)
    owner = xform.user

    def set_form():
        form = QuickConverter(request.POST, request.FILES)
        survey = form.publish(request.user, id_string).survey
        enketo_webform_url = reverse(
            enter_data,
            kwargs={'username': username, 'id_string': survey.id_string}
        )
        audit = {
            'xform': xform.id_string
        }
        audit_log(
            Actions.FORM_XLS_UPDATED, request.user, owner,
            _("XLS for '%(id_string)s' updated.") %
            {
                'id_string': xform.id_string,
            }, audit, request)
        return {
            'type': 'alert-success',
            'text': _(u'Successfully published %(form_id)s.'
                      u' <a href="%(form_url)s">Enter Web Form</a>'
                      u' or <a href="#preview-modal" data-toggle="modal">'
                      u'Preview Web Form</a>')
                    % {'form_id': survey.id_string,
                       'form_url': enketo_webform_url}
        }

    message = publish_form(set_form)
    messages.add_message(
        request, messages.INFO, message['text'], extra_tags=message['type'])

    return HttpResponseRedirect(reverse(show, kwargs={
        'username': username,
        'id_string': id_string
    }))


@is_owner
def activity(request, username):
    owner = get_object_or_404(User, username=username)

    return render(request, 'activity.html', {'user': owner})


def activity_fields(request):
    fields = [
        {
            'id': 'created_on',
            'label': _('Performed On'),
            'type': 'datetime',
            'searchable': False
        },
        {
            'id': 'action',
            'label': _('Action'),
            'type': 'string',
            'searchable': True,
            'options': sorted([Actions[e] for e in Actions.enums])
        },
        {
            'id': 'user',
            'label': 'Performed By',
            'type': 'string',
            'searchable': True
        },
        {
            'id': 'msg',
            'label': 'Description',
            'type': 'string',
            'searchable': True
        },
    ]
    response_text = json.dumps(fields)

    return HttpResponse(response_text, content_type='application/json')


@is_owner
def activity_api(request, username):
    from bson.objectid import ObjectId

    def stringify_unknowns(obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.strftime(DATETIME_FORMAT)
        return None

    try:
        query_args = {
            'username': username,
            'query': json.loads(request.GET.get('query'))
            if request.GET.get('query') else {},
            'fields': json.loads(request.GET.get('fields'))
            if request.GET.get('fields') else [],
            'sort': json.loads(request.GET.get('sort'))
            if request.GET.get('sort') else {}
        }
        if 'start' in request.GET:
            query_args["start"] = int(request.GET.get('start'))
        if 'limit' in request.GET:
            query_args["limit"] = int(request.GET.get('limit'))
        if 'count' in request.GET:
            query_args["count"] = True \
                if int(request.GET.get('count')) > 0 else False
        cursor = AuditLog.query_mongo(**query_args)
    except ValueError as e:
        return HttpResponseBadRequest(e.__str__())

    records = list(record for record in cursor)
    response_text = json.dumps(records, default=stringify_unknowns)
    if 'callback' in request.GET and request.GET.get('callback') != '':
        callback = request.GET.get('callback')
        response_text = ("%s(%s)" % (callback, response_text))

    return HttpResponse(response_text, content_type='application/json')


def qrcode(request, username, id_string):
    try:
        formhub_url = "http://%s/" % request.META['HTTP_HOST']
    except:
        formhub_url = "http://formhub.org/"
    formhub_url = formhub_url + username

    if settings.TESTING_MODE:
        formhub_url = "https://{}/{}".format(settings.TEST_HTTP_HOST,
                                             settings.TEST_USERNAME)

    results = _(u"Unexpected Error occured: No QRCODE generated")
    status = 200
    try:
        url = enketo_url(formhub_url, id_string)
    except Exception as e:
        error_msg = _(u"Error Generating QRCODE: %s" % e)
        results = """<div class="alert alert-error">%s</div>""" % error_msg
        status = 400
    else:
        if url:
            image = generate_qrcode(url)
            results = """<img class="qrcode" src="%s" alt="%s" />
                    </br><a href="%s" target="_blank">%s</a>""" \
                      % (image, url, url, url)
        else:
            status = 400

    return HttpResponse(results, content_type='text/html', status=status)


def enketo_preview(request, username, id_string):
    xform = get_object_or_404(
        XForm, user__username__iexact=username, id_string__exact=id_string)
    owner = xform.user
    if not has_permission(xform, owner, request, xform.shared):
        return HttpResponseForbidden(_(u'Not shared.'))
    enekto_preview_url = \
        "%(enketo_url)s?server=%(profile_url)s&id=%(id_string)s" % {
            'enketo_url': settings.ENKETO_PREVIEW_URL,
            'profile_url': request.build_absolute_uri(
                reverse(profile, kwargs={'username': owner.username})),
            'id_string': xform.id_string
        }
    return HttpResponseRedirect(enekto_preview_url)


@require_GET
@login_required
def username_list(request):
    data = []
    query = request.GET.get('query', None)
    if query:
        users = User.objects.values('username') \
            .filter(username__startswith=query, is_active=True, pk__gte=0)
        data = [user['username'] for user in users]

    return HttpResponse(json.dumps(data), content_type='application/json')


def form_replace(request, username, id_string):
    if request.method == 'POST':
        xform = get_object_or_404(XForm, user__username__iexact=username, id_string__exact=id_string)
        owner = xform.user

        def set_form():
            form = QuickConverter(request.POST, request.FILES)

            survey = form.publish(request.user, id_string).survey

            enketo_webform_url = reverse(
                enter_data,
                kwargs={'username': username, 'id_string': survey.id_string}
            )
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_XLS_UPDATED, request.user, owner,
                _("XLS for '%(id_string)s' updated.") %
                {
                    'id_string': xform.id_string,
                }, audit, request)
            return {
                'type': 'alert-success',
                'text': _(u'Successfully published %(form_id)s.'
                          u' <a href="%(form_url)s">Enter Web Form</a>'
                          u' or <a href="#preview-modal" data-toggle="modal">'
                          u'Preview Web Form</a>')
                        % {'form_id': survey.id_string,
                           'form_url': enketo_webform_url}
            }

        message = publish_form(set_form)

        if message['type'] == 'alert-success':
            request.POST['username'] = username
            request.POST['form_id_string'] = id_string
            auto_reload_xlsform(request, username, id_string)
            xform = get_object_or_404(XForm, user__username__iexact=username, id_string__exact=id_string)
            # root = ET.fromstring(xform.xml)
            root = ET.fromstring(xform.xml.encode('utf-8'))
            # printRecur(root,0,'',form_result['form_id_string'])
            parseXML(root, 0, '', id_string)
            global field_list
            cursor = connection.cursor()
            qry_parse = "select * from get_xform_extracted(" + str(xform.id) + ",'" + field_list + "')"
            cursor.execute(qry_parse)
            cursor.close()

            generate_or_update_flat_table(xform.id)

        messages.add_message(
            request, messages.INFO, message['text'], extra_tags=message['type'])
        HttpResponseRedirect('/')

    return render(request, "form_upload.html")


def parseXML(root, ins, parent, form_id):
    global field_list

    is_instance = 0
    pnt = ''
    """Recursively prints the tree."""
    # if root.tag in ignoreElems:
    #    return
    # print ' '*indent + '%s: %s' % (root.tag.title(), root.attrib.get('name', root.text))
    s_tag = '%s' % (root.tag)
    # print ' '*indent + '%s' % (root.tag)
    if s_tag == '{http://www.w3.org/2002/xforms}instance':
        # print 'here-1'
        is_instance = 1
    elif ins == 1:
        # print 'here-2'
        is_instance = 1
    elif ins == 2:
        is_instance = 2
    else:
        is_instance = 0

    if ins == 2:
        if parent == '':
            # print '%s' %(s_tag.replace("{http://www.w3.org/2002/xforms}", ""))
            fld = '%s' % (s_tag.replace("{http://www.w3.org/2002/xforms}", ""))
            if field_list == '':
                field_list = fld
            else:
                field_list = field_list + ',' + fld
            pnt = '%s' % (s_tag.replace("{http://www.w3.org/2002/xforms}", ""))

        else:
            fld = '%s/%s' % (parent, s_tag.replace("{http://www.w3.org/2002/xforms}", ""))
            if field_list == '':
                field_list = fld
            else:
                field_list = field_list + ',' + fld

            # print '%s/%s' %(parent,s_tag.replace("{http://www.w3.org/2002/xforms}", ""))
            pnt = '%s/%s' % (parent, s_tag.replace("{http://www.w3.org/2002/xforms}", ""))
    if 'id' in root.attrib:
        if root.attrib['id'] == form_id and ins == 1:
            is_instance = 2
            ins = 2

            # if s_tag.replace("{http://www.w3.org/2002/xforms}", "")==form_id and ins==1:
            # print 'here'
            # is_instance=2
            # ins=2

    # indent += 4
    for elem in root.getchildren():
        parseXML(elem, is_instance, pnt, form_id)
        # indent -= 4


@login_required
def survey_summary(request):
    # instance_parse()
    surveyData = {}
    permission_data = {}
    ownership = {}
    totalSubmission = []
    surveyObj = []

    # frm_qry="select xform_id from vwrolewiseformpermission where username='"+str(request.user)+"'"
    # cursor = connection.cursor()
    # cursor.execute(frm_qry)
    # tmp_db_value = cursor.fetchall()
    # frm_list=[]
    # if tmp_db_value is not None:
    #    for every in tmp_db_value:
    #        frm_list.append(every[0])
    # xforms = XForm.objects.filter(reduce(operator.or_, [Q(id=c) for c in frm_list]))

    xforms = get_xform_list(str(request.user))

    # xforms = get_viewable_projects(request)
    # print xforms

    _DATETIME_FORMAT_SUBMIT = '%Y-%m-%d'
    cursor = connection.cursor()
    for xform in xforms:
        surveyObj.append(xform)
        form_id = str(xform.id_string)
        is_owner = xform.user == request.user
        users_with_perms = []

        pqry = "SELECT  can_edit,can_view,can_submit,can_delete,can_setting	FROM vwrolewiseformpermission where  xform_id=" + str(
            xform.id) + " and username='" + str(request.user) + "'"

        cursor.execute(pqry)

        tmp_db_value = cursor.fetchall()
        frm_list = []

        if tmp_db_value is not None:
            for every in tmp_db_value:
                has_perm = []
                if str(every[0]) == '1':
                    has_perm.append("Can Edit")
                if str(every[1]) == '1':
                    has_perm.append("Can View")
                if str(every[2]) == '1':
                    has_perm.append("Can submit to")
                users_with_perms.append(str(request.user) + "|" + "|".join(has_perm))
                permission_data[str(form_id)] = users_with_perms

        #print users_with_perms
        #print permission_data
        owner_data = []
        owner_data.append(is_owner)
        owner_data.append(xform.user.username)
        owner_data.append(request.user.username)
        ownership[form_id] = owner_data
        submission_date_query = "SELECT (json->>'_submission_time')::timestamp::date AS day_of_submission FROM logger_instance WHERE deleted_at is null and xform_id=" + str(
            xform.id) + ""
        cursor.execute(submission_date_query)
        fetchVal = cursor.fetchall();
        rowcount = cursor.rowcount
        date = []
        if rowcount == 0:
            date.append('no submission')
            surveyData[form_id] = date
        else:
            for each in fetchVal:
                date.append(each[0].strftime(_DATETIME_FORMAT_SUBMIT))
                surveyData[form_id] = date
                # print '----------surveyObj----------'
    # print surveyData

    variables = RequestContext(request, {
        'head_title': 'Project Summary',
        'total_submission': totalSubmission,
        'surveyObj': surveyObj,
        'surveydata': json.dumps(surveyData),
        'ownership': json.dumps(ownership),
        'permission': json.dumps(permission_data),
        'username': request.user.username
    })
    output = render(request, 'survey_summary.html', variables);
    cursor.close()
    return HttpResponse(output)


def get_recursive_organization_children(organization, organization_list=[]):
    organization_list.append(organization)
    observables = Organizations.objects.filter(parent_organization=organization)
    for org in observables:
        if org not in organization_list:
            organization_list = list((set(get_recursive_organization_children(org, organization_list))))
    return list(set(organization_list))


def __db_fetch_values(query):
    cursor = connection.cursor()
    cursor.execute(query)
    fetchVal = cursor.fetchall()
    cursor.close()
    return fetchVal


def __db_fetch_single_value(query):
    cursor = connection.cursor()
    cursor.execute(query)
    fetchVal = cursor.fetchone()
    cursor.close()
    return fetchVal[0]


def __db_fetch_values_dict(query):
    cursor = connection.cursor()
    cursor.execute(query)
    fetchVal = dictfetchall(cursor)
    cursor.close()
    return fetchVal


def __db_commit_query(query):
    cursor = connection.cursor()
    cursor.execute(query)
    cursor.close()


def __db_insert_query(query):
    cursor = connection.cursor()
    cursor.execute(query)
    # connection.commit()
    fetch_val = cursor.fetchone()
    cursor.close()
    return fetch_val[0]


def dictfetchall(cursor):
    desc = cursor.description
    return [
        OrderedDict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()]


def decimal_date_default(obj):
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    elif hasattr(obj, 'isoformat'):
        return obj.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    else:
        return obj
    raise TypeError


@login_required
def add_form(request, id_string):
    """
        Function for rendering odk forms from form parser through iFrame

        Args:
            request (str): Default Django request Object
            id_string (str): form id_string
        Returns:
            Render iFrame within Html
    """
    username = request.user
    # if in local environment, you should use your ip instead of localhost
    # server_address = request.META.get('ip')+':'+request.META.get('HTTP_HOST').split(':', 1)[1]
    # when in developement/live/client server
    server_address = KOBO_MODULE_URL
    kobo_server = KOBO_SERVER
    web_address = WEB_SERVER
    # server_address = 'localhost:8007'
    # parse request param
    request_param = request.GET.dict()
    # server_address = '192.168.22.133:8001'
    print(server_address)
    # form_builder_server = database_utility.__db_fetch_single_value("select form_builder_server from form_builder_configuration")
    form_id = __db_fetch_single_value(
        "select id from logger_xform where id_string='" + id_string + "'")
    form_renderer_server = settings.FORM_RENDERER_SERVER
    return render(request, 'add_form.html',
                  {'username': username, 'web_address': web_address, 'kobo_server': kobo_server, 'form_id': form_id,
                   'form_builder_server': form_renderer_server, 'request_param': json.dumps(request_param)})


@login_required
def form_designer(request):
    username = request.user
    return render(request, 'form_designer.html',{'username': username})


def check_valid_id_string(id_string):
    """
    Check provided id_string is unique
    Args:
        id_string (str): form id_string
    Returns:
        (bool) True if id_string is unique
    """
    cnt = __db_fetch_single_value("""
    select count(*) from instance.logger_xform where id_string = '%s'
    """ % id_string)
    if cnt > 0:
        return False
    else:
        unpub_cnt = __db_fetch_single_value("""
                select count(*) from core.form_builder_forms where form_id_string = '%s'
                """ % id_string)
        if unpub_cnt > 0:
            return False
        else:
            return True


def is_json(json_data):
    try:
        json.loads(json_data)
    except ValueError as e:
        return False
    return True


@csrf_exempt
def uiformbuilder_add_form_json(request, username):
    """
    function for adding new form builder json
    Args:
        request (str): Default Django request Object
    Returns:

    """
    user = User.objects.get(username=username)
    if user:
        req_body = json.loads(request.body)
        user_id = user.id
        if 'form_id_string' in req_body:
            form_id_string = req_body['form_id_string']
            if 'form_title' in req_body:
                form_title = req_body['form_title']
            else:
                form_title = form_id_string
            if check_valid_id_string(form_id_string):
                if 'form_json' in req_body:
                    form_json = req_body['form_json']
                    if is_json(json.dumps(form_json)):
                        ui_form_id = __db_insert_query("""
                        INSERT INTO core.form_builder_forms
                        (form_title, form_json, form_id_string, created_at, created_by, publish_status)
                        VALUES('%s','%s'::json, '%s', now(), %s, 0) returning id
                        """ % (form_title, json.dumps(form_json), form_id_string, user_id))
                        msg = 'Successfully added new form'
                        http_status = status.HTTP_200_OK
                    else:
                        msg = 'Form JSON is not valid'
                        http_status = status.HTTP_400_BAD_REQUEST
                else:
                    msg = 'Form JSON is required'
                    http_status = status.HTTP_400_BAD_REQUEST
            else:
                msg = 'This id_string is already in use'
                http_status = status.HTTP_400_BAD_REQUEST
        else:
            msg = 'Please provide an id_string as unique form identifier'
            http_status = status.HTTP_204_NO_CONTENT
    else:
        msg = 'Invalid username'
        http_status = status.HTTP_401_UNAUTHORIZED

    resp = {
        'msg': msg,
        'status': http_status
    }
    return HttpResponse(json.dumps(resp))


@csrf_exempt
def uiformbuilder_update_form_json(request, username):
    user = User.objects.get(username=username)
    if user:
        req_body = json.loads(request.body)
        user_id = user.id
        if 'form_id' in req_body:
            form_id = req_body['form_id']
            form_cnt = __db_fetch_single_value("""
            select count(*) from core.form_builder_forms where id = %s
            """ % form_id)
            if form_cnt > 0:
                if 'form_id_string' in req_body:
                    update_form_id_string = req_body['form_id_string']
                else:
                    update_form_id_string = __db_fetch_single_value("""
                    select form_id_string from core.form_builder_forms where id = %s
                    """ % form_id)

                if 'form_title' in req_body:
                    update_form_title = req_body['form_title']
                else:
                    update_form_title = __db_fetch_single_value("""
                    select form_title from core.form_builder_forms where id = %s
                    """ % form_id)

                if 'form_json' in req_body:
                    form_json = req_body['form_json']
                    if is_json(json.dumps(form_json)):
                        publish_status = __db_fetch_single_value("""
                        select publish_status from core.form_builder_forms where id = %s
                        """ % form_id)
                        if publish_status == 0:
                            __db_commit_query("""
                            UPDATE core.form_builder_forms
                            SET form_title='%s', form_id_string='%s', updated_at=NOW(), updated_by=%s, form_json='%s'::json
                            WHERE id=%s
                            """ % (update_form_title, update_form_id_string, user_id, json.dumps(form_json), form_id))
                            msg = 'Success'
                            http_status = status.HTTP_200_OK
                        else:
                            published_id_string = __db_fetch_single_value("""
                            select form_id_string from core.form_builder_forms where id = %s
                            """ % form_id)
                            if published_id_string != req_body['form_id_string']:
                                msg = 'You cannot change id string for published forms'
                                http_status = status.HTTP_401_UNAUTHORIZED
                            else:
                                __db_commit_query("""
                                                            UPDATE core.form_builder_forms
                                                            SET form_title='%s', form_id_string='%s', updated_at=NOW(), updated_by=%s, form_json='%s'::json
                                                            WHERE id=%s
                                                            """ % (
                                update_form_title, update_form_id_string, user_id, json.dumps(form_json), form_id))
                                msg = 'Success'
                                http_status = status.HTTP_200_OK
                                # __db_commit_query("""
                                #                             UPDATE core.form_builder_forms
                                #                             SET form_title='%s', form_id_string='%s', updated_at=NOW(), updated_by=%s, form_json='%s'::json
                                #                             WHERE id=%s
                                #                             """ % (
                                #     update_form_title, update_form_id_string, user_id, json.dumps(form_json), form_id))
                                # #####################
                                # # Form Publish Code #
                                # #####################
                                # form_title, form_id_string, json_str = fetch_form_instance(form_id)
                                # xls_path = uiform_publish.publish_ui_form(json_str, form_title, form_id_string)
                                # files = {'xls_file': open(xls_path, 'rb')}
                                # r = requests.post('http://' + str(request.META['HTTP_HOST']) + '/' + str(
                                #     username) + '/form_replace_from_ui/'+str(form_id_string)+'/',
                                #                   files=files)
                                # if r.status_code == 200:
                                #     msg = 'Form republished sucessfully'
                                #     http_status = status.HTTP_200_OK
                                # else:
                                #     print str(r)
                                #     msg = 'Form Publish Failed'
                                #     http_status = status.HTTP_500_INTERNAL_SERVER_ERROR

                    else:
                        msg = 'Form JSON is not valid'
                        http_status = status.HTTP_400_BAD_REQUEST
                else:
                    msg = 'Form JSON is required'
                    http_status = status.HTTP_400_BAD_REQUEST

            else:
                msg = 'Invalid Form Id provided'
                http_status = status.HTTP_400_BAD_REQUEST
        else:
            msg = 'Form Id is required'
            http_status = status.HTTP_204_NO_CONTENT
    else:
        msg = 'Invalid username'
        http_status = status.HTTP_401_UNAUTHORIZED

    resp = {
        'msg': msg,
        'status': http_status
    }
    return HttpResponse(json.dumps(resp))


@csrf_exempt
def uiformbuilder_list_form_json(request, username):
    user = User.objects.get(username=username)
    req_body = json.loads(request.body)
    if 'page_length' in req_body:
        page_length = req_body['page_length']
    else:
        page_length = 10

    if 'page_number' in req_body:
        page_number = req_body['page_number']
    else:
        page_number = 1

    tnt_cnt = __db_fetch_single_value("""
    select count(*) from core.form_builder_forms where created_by = %s
    """ % user.id)

    form_data = []
    if user:
        form_data = __db_fetch_values_dict("""
        select id as form_id,form_title,form_id_string,form_json,created_at,publish_status from core.form_builder_forms where created_by = %s
        limit %s offset %s * (%s - 1)
        """ % (user.id, page_length, page_length, page_number))
        msg = 'Success'
        http_status = status.HTTP_200_OK
    else:
        msg = 'Invalid username'
        http_status = status.HTTP_401_UNAUTHORIZED

    resp = {
        'page_length': page_length,
        'page_number': page_number,
        'tnt_cnt': tnt_cnt,
        'forms': form_data,
        'msg': msg,
        'status': http_status
    }
    return HttpResponse(json.dumps(resp, default=decimal_date_default))


@csrf_exempt
def uiformbuilder_publish_form_json(request, username):
    user = User.objects.get(username=username)
    if user:
        req_body = json.loads(request.body)
        user_id = user.id
        if 'form_id' in req_body:
            form_id = req_body['form_id']
            form_cnt = __db_fetch_single_value("""
            select count(*) from core.form_builder_forms where id = %s
            """ % form_id)
            if form_cnt > 0:
                publish_status = __db_fetch_single_value("""
                                        select publish_status from core.form_builder_forms where id = %s
                                        """ % form_id)
                form_title, form_id_string, json_str = fetch_form_instance(form_id)
                xls_path = uiform_publish.publish_ui_form(json_str, form_title, form_id_string)
                files = {'xls_file': open(xls_path, 'rb')}
                if publish_status == 0:
                    r = requests.post('http://' + str(request.META['HTTP_HOST']) + '/' + str(username) + '/form_publish_from_ui/',
                               files=files)
                    if r.status_code == 200:
                        __db_commit_query("""
                        update core.form_builder_forms set publish_status = %s where id = %s
                        """ % (1,form_id))
                        msg = 'Form published sucessfully'
                        http_status = status.HTTP_200_OK
                    else:
                        print str(r)
                        msg = 'Form Publish Failed'
                        http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
                else:
                    r = requests.post('http://' + str(request.META['HTTP_HOST']) + '/' + str(
                        username) + '/form_replace_from_ui/'+str(form_id_string)+'/',
                                      files=files)
                    if r.status_code == 200:
                        msg = 'Form republished sucessfully'
                        http_status = status.HTTP_200_OK
                    else:
                        print str(r)
                        msg = 'Form Publish Failed'
                        http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
            else:
                msg = 'Invalid Form Id provided'
                http_status = status.HTTP_400_BAD_REQUEST
        else:
            msg = 'Form Id is required'
            http_status = status.HTTP_204_NO_CONTENT

        resp = {
            'msg': msg,
            'status': http_status
        }
        return HttpResponse(json.dumps(resp))


def fetch_form_instance(form_id):
    forms_data = __db_fetch_values_dict("""
    select form_title,form_id_string,form_json::text from core.form_builder_forms where id = %s
    """ % form_id)
    return forms_data[0]['form_title'], forms_data[0]['form_id_string'], forms_data[0]['form_json']
