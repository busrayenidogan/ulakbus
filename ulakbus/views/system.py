# -*-  coding: utf-8 -*-
"""
"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.

from pyoko.modelmeta import model_registry
from pyoko.conf import settings
from ulakbus.lib.cache import PersonelIstatistik, RaporlamaEklentisi

from ulakbus.views.reports import ReporterRegistry
from zengine.lib.decorators import view
from zengine.views.base import SysView
from zengine.lib.translation import gettext as _
from ulakbus.models import Personel, Ogrenci
from zengine.views.menu import Menu

from datetime import datetime
import json


class Search(SysView):
    SEARCH_ON = None
    PATH = None

    def __init__(self, *args, **kwargs):
        super(Search, self).__init__(*args, **kwargs)
        self.query = self.current.input['query_params']
        self.output['results'] = []
        self.do_search()

    def do_search(self):
        try:
            tckn = int(self.query['q'].strip())
            self.query['tckn__startswith'] = tckn
            del self.query['q']
            objects = self.SEARCH_ON.objects.filter(**self.query).values('ad', 'soyad', 'tckn',
                                                                         'key')
        except ValueError:
            q = self.query.pop('q').split(" ")
            objects = []
            if len(q) == 1:
                # query Ali, Ayşe, Demir gibi boşluksuz bir string
                # içeriyorsa, ad ve soyad içerisinde aranmalıdır.
                objects = self.SEARCH_ON.objects.search_on(
                    'ad', 'soyad', contains=q[0]).filter(**self.query).values('ad', 'soyad', 'tckn',
                                                                              'key')

            if len(q) > 1:
                # query Ali Rıza, Ayşe Han Demir, Neşrin Hasibe Gül Yakuphanoğullarından
                # gibi boşluklu cok parçali bir string ise, öncelikle son parça soyad ile
                # `contains`, önceki parçalar ise isim ile `contains` şeklinde
                # aranmalıdır. Sonuç bulunamaz ise tüm parçalar isim ile
                # `contains` şeklinde aranmalıdır.
                objects = self.SEARCH_ON.objects.search_on(
                    'ad', contains=" ".join(q[:-1])).search_on(
                    'soyad', contains=q[-1]).filter(**self.query).values('ad', 'soyad', 'tckn',
                                                                         'key')

                objects_by_name = []
                if not objects:
                    objects = self.SEARCH_ON.objects.search_on(
                        'ad', contains=" ".join(q)).filter(**self.query).values('ad', 'soyad',
                                                                                'tckn', 'key')

        self.output['results'] = [("{ad} {soyad}".format(**o), o['tckn'], o['key'], '') for o in
                                  objects]


# @basic_view('ogrenci_ara')
class SearchStudent(Search):
    PATH = 'ogrenci_ara'
    SEARCH_ON = Ogrenci


class SearchPerson(Search):
    PATH = 'personel_ara'
    SEARCH_ON = Personel


class GetCurrentUser(SysView):
    PATH = 'get_current_user'

    def __init__(self, current):
        super(GetCurrentUser, self).__init__(current)
        self.output['current_user'] = {}
        self.getUser(current.user)

    def getUser(self, userObject):
        currentUser = {
            "name": userObject.name,
            "surname": userObject.surname,
            "username": userObject.username,
            "roles": [{"role": role.__unicode__()} for role in userObject.role_set]
        }
        self.output['current_user'] = currentUser


class UlakbusMenu(Menu):
    PATH = 'dashboard'

    def __init__(self, current):
        super(UlakbusMenu, self).__init__(current)
        self.add_reporters()
        self.add_user_data()
        self.add_settings()
        self.add_widgets()
        self.add_admin_crud()

    def add_admin_crud(self):
        if self.current.user.superuser:
            for mdl in model_registry.get_base_models():
                self.output['other'].append({
                    "text": mdl.Meta.verbose_name_plural,
                    "wf": 'crud',
                    "model": mdl.__name__,
                    "kategori": 'Admin'})

    def add_settings(self):
        self.output['settings'] = {
            'static_url': settings.S3_PUBLIC_URL,
        }

    def add_user_data(self):
        # add data of current logged in user
        usr = self.current.user
        role = self.current.role
        usr_total_roles = [{"role": roleset.role.__unicode__()} for roleset in
                           self.current.user.role_set]
        self.output['current_user'] = {
            "name": usr.name,
            "surname": usr.surname,
            "username": usr.username,
            "role": self.current.role.abstract_role.name,
            "avatar": usr.get_avatar_url(),
            "is_staff": role.is_staff,
            "is_student": role.is_student,
            "roles": usr_total_roles,
            "role_details": {'unit_name': role.unit.name,
                             'abs_name': role.abstract_role.name,
                             'role_count': len(usr_total_roles)}
        }

        if role.is_student:
            # insert student specific data here
            self.output['current_user'].update({
            })

        elif role.is_staff:
            # insert staff specific data here
            self.output['current_user'].update({
            })

    def add_widgets(self):
        self.output['widgets'] = []

        if self.output.get('personel', False):
            self.output['widgets'].append({
                "view": "personel_ara",
                "type": "searchbox",
                "title": "Personel",
                "checkboxes": [
                    {"label": "Pasif Personeller İçinde Ara", "name": "arsiv",
                     "value": True, "checked": False}]
            })

            self.output['widgets'].append({
                "type": "table",
                "title": "Genel Personel İstatistikleri",
                "rows": get_general_staff_stats()
            })

        if self.output.get('ogrenci', False):
            self.output['widgets'].append({
                "view": "ogrenci_ara",
                "type": "searchbox",
                "title": "Ogrenci",
            })

    def add_reporters(self):
        for mdl in ReporterRegistry.get_reporters():
            perm = "report.%s" % mdl['model']
            if self.current.has_permission(perm):
                self.output['other'].append(mdl)


def get_general_staff_stats():
    """
       List the stats for all staff in the system.
       Returns:
           list of stats
    """
    d = PersonelIstatistik().get_or_set()
    rows = []
    for row in [
        ['', _(u"Toplam"), _(u"Kadın"), _(u"Erkek")],
        [_(u"Personel"), d['total_personel'], d['kadin_personel'], d['erkek_personel']],
        [_(u"Akademik"), d['akademik_personel'], d['akademik_personel_kadin'],
         d['akademik_personel_erkek']],
        [_(u"İdari"), d['idari_personel'], d['idari_personel_kadin'], d['idari_personel_erkek']],
        [_(u"Yardımcı Doçent"), d['yar_doc_total'], d['yar_doc_kadin'], d['yar_doc_erkek']],
        [_(u"Doçent"), d['doc_total'], d['doc_kadin'], d['doc_erkek']],
        [_(u"Profesör"), d['prof_total'], d['prof_kadin'], d['prof_erkek']],
        [_(u"Araştırma Görevlisi"), d['ar_gor_total'], d['ar_gor_kadin'], d['ar_gor_erkek']],
        [_(u"Engelli"), d['engelli_personel_total'], d['engelli_personel_kadin'],
         d['engelli_personel_erkek']]]:
        cols = []
        for col in row:
            cols.append(
                {"content": col}
            )
        rows.append({
            "cols": cols
        })
    return rows


@view()
def get_report_data(current):
    """
        Populates the report screen data.

        .. code-block:: python

               #  request:
                   {
                   'view': '_zops_get_report_data',
                    selectors: [
                            {
                                name: "some field name (name, age etc)",
                                checked: true or false
                            },
                            {
                                name: "some field name (name, age etc)",
                                checked: true or false
                            },
                            {
                                name: "some field name (name, age etc)",
                                checked: true or false
                            },
                            ...
                        ],
                    options: {
                            some_input_field: {
                                condition: "CONTAINS", // or "STARTS_WITH", "END_WIDTH"
                                value: "some value"
                            },
                            some_select_field: {
                                value: "some value"
                            },
                            some_multiselect_field: {
                                some_name: "some value",
                                some_name: "some value",
                                some_name: "some value",
                                ...
                            },
                            some_range_field: {
                                start (or min): "some value",
                                end (or max): "some value"
                            }
                        }
                   }

               #  response:
                    {
                            'gridOptions': {
                                enableSorting: true,
                                useExternalSorting: true,  //if need sorting from backend side
                                enableFiltering: true,
                                toggleFiltering: true,
                                useExternalFiltering: true, //if need filtering from backend side
                                paginationPageSize: 25,
                                useExternalPagination: true, //if need paginations from backend side
                                enableAdding: true,
                                enableRemoving: true,
                                selectors: [
                                    {
                                        name: "some field name (name, age etc)",
                                        checked: true or false
                                    },
                                    {
                                        name: "some field name (name, age etc)",
                                        checked: true or false
                                    },
                                    {
                                        name: "some field name (name, age etc)",
                                        checked: true or false
                                    },
                                    ...
                                ],
                                columnDefs: [
                                    // input contain filter example
                                    {
                                        field: "age",
                                        type: "INPUT"
                                        filter: {
                                            condition: "CONTAINS",
                                            placeholder: "contains"
                                        }
                                    },
                                    // multiple input filters example
                                    {
                                        field: "age",
                                        type: "INPUT",
                                        filter: {
                                            condition: "STARTS_WITH",
                                            placeholder: "starts with"
                                        }
                                    },
                                    {
                                        field: "age",
                                        type: "INPUT",
                                        filter: {
                                            condition: "ENDS_WITH",
                                            placeholder: "ends with"
                                        }
                                    },
                                    // range input integer example
                                    {
                                        field: "age",
                                        type: "range",
                                        rangeType: "integer",
                                        filters: [
                                            {
                                                condition: "MAX",
                                                placeholder: "max value"
                                            },
                                            {
                                                condition: "MIN",
                                                placeholder: "min value"
                                            }
                                        ]
                                    },
                                    // range input datetime example
                                    {
                                    field: "date",
                                    type: "range",
                                    rangeType: "datetime",
                                    filters: [
                                            {
                                                condition: "START",
                                                placeholder: "start date"
                                            },
                                            {
                                                condition: "END",
                                                placeholder: "end date"
                                            }
                                        ]
                                    },
                                    // select
                                    {
                                    field: 'gender',
                                    filter: {
                                        term: '2',
                                        type: 'SELECT',
                                        selectOptions: [ { value: '1', label: 'male' }, { value: '2', label: 'female' }, { value: '3', label: 'unknown'} ]
                                    },
                                    // multiselect
                                    {
                                        field: 'graduation',
                                        filter: {
                                        type: 'MULTISELECT',
                                        selectOptions: [ { value: 'university', label: 'university' }, { value: 'high school', label: 'high school' } ]
                                    },
                                    // examples for editing
                                    { field: 'last_name', enableCellEdit: true },
                                    { field: 'age', enableCellEdit: true, type: 'number'},
                                    { field: 'registered', displayName: 'Registered' , type: 'date'},
                                    { field: 'address', displayName: 'Address', type: 'object'}, //not editable if type==='object'
                                    { field: 'address.city', enableCellEdit: true, displayName: 'Address (even rows editable)' }
                                    { field: 'isActive', enableCellEdit: true, type: 'boolean'},
                                ],
                                initialData: [
                                    {
                                        "name": "Cox",
                                        "company": "Enormo",
                                        "gender": "male",
                                        "graduation": "university",
                                        ...
                                    },
                                    {
                                        "name": "Lorraine",
                                        "company": "Comveyer",
                                        "gender": "female",
                                        "graduation": "high school",
                                        ...
                                    },
                                    {
                                        "name": "Nancy",,
                                        "company": "Fuelton",
                                        "gender": "female",
                                        "graduation": "university",
                                        ...
                                    },
                                        {
                                        "name": "Misty",
                                        "company": "Letpro",
                                        "gender": "female",
                                        "graduation": "university",
                                        ...
                                    }
                                ]
                        }
                    }
    """

    if len(current.input) <= 1:
        cache_obj = {}
        cache_obj['gridOptions'] = RaporlamaEklentisi().get_or_set()['gridOptions']
        current.output = cache_obj
    else:
        raporlama_cache = RaporlamaEklentisi().get_or_set()
        alan_filter_type_map = raporlama_cache['alan_filter_type_map']
        time_related_fields = raporlama_cache['time_related_fields']
        options = current.input['options']
        query_params = {}
        for f, qp in options.items():
            if alan_filter_type_map[f] == "INPUT-CONTAINS":
                query_params[f + "__contains"] = qp['value']
            elif alan_filter_type_map[f] == "SELECT":
                query_params[f] = qp['value']
            elif alan_filter_type_map[f] == "MULTISELECT":
                multiselect_list = []
                for msi in qp:
                    multiselect_list.append(msi)
                query_params[f + "__in"] = multiselect_list
            elif alan_filter_type_map[f] == "RANGE-DATETIME":
                date_format = "%d.%m.%Y"
                start_raw = str(qp['start'])
                start = datetime.strptime(start_raw, date_format)
                starts = start_raw.split(".")
                end_raw = str(qp['end'])
                end = datetime.strptime(end_raw, date_format)
                ends = end_raw.split(".")
                query_params[f + "__range"] = [start, end]
            elif alan_filter_type_map[f] == "RANGE-INTEGER":
                min = qp['min']
                max = qp['max']
                query_params[f + "__range"] = [int(min), int(max)]
            elif alan_filter_type_map[f] == "INPUT-STARTS-WITH":
                query_params[f + "__startswith"] = qp['value']

        result_set = Personel.objects.filter(**query_params)

        selectors = current.input['selectors']
        active_selectors = []
        for selector in selectors:
            if selector['checked']:
                active_selectors.append(selector['name'])

        initial_data = []
        for p in result_set:
            pd = {}
            p_ = p.clean_value()
            for active_selector in active_selectors:
                if active_selector in time_related_fields:
                    date_f = "%Y-%d-%mT%H:%M:%SZ"
                    date_str = p_[active_selector]
                    d = datetime.strptime(date_str, date_f).date()
                    pd[active_selector] = d.strftime(date_format)
                else:
                    pd[active_selector] = p_[active_selector]
            initial_data.append(pd)

        current.output['initialData'] = initial_data




