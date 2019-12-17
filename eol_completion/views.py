# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import six
import json

from datetime import datetime
from courseware.courses import get_course_with_access
from django.template.loader import render_to_string
from django.shortcuts import render_to_response
from web_fragments.fragment import Fragment
from django.core.cache import cache
from openedx.core.djangoapps.plugin_api.views import EdxFragmentView
from lms.djangoapps.certificates.models import GeneratedCertificate
from xblock.fields import Scope
from opaque_keys.edx.keys import CourseKey, UsageKey
from opaque_keys import InvalidKeyError
from django.contrib.auth.models import User

from xblock_discussion import DiscussionXBlock
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.inheritance import compute_inherited_metadata, own_metadata

from completion.models import BlockCompletion
from collections import OrderedDict
# Create your views here.

FILTER_LIST = ['xml_attributes']
INHERITED_FILTER_LIST = ['children', 'xml_attributes']


class EolCompletionFragmentView(EdxFragmentView):
    def render_to_fragment(self, request, course_id, **kwargs):

        context = self.get_context(request, course_id)
        html = render_to_string(
            'eol_completion/eol_completion_fragment.html', context)
        fragment = Fragment(html)
        return fragment

    def get_context(self, request, course_id):        
        course_key = CourseKey.from_string(course_id)
        course = get_course_with_access(request.user, "load", course_key)
        enrolled_students = User.objects.filter(
            courseenrollment__course_id=course_key,
            courseenrollment__is_active=1
        ).order_by('username').values('id', 'username', 'email')
        store = modulestore()
        # diccionario con todos los bloques del curso
        info = self.dump_module(store.get_course(course_key))

        curso_aux = course_id.split(":", 1)
        id_curso = 'block-v1:' + curso_aux[1] + '+type@course+block@course'
        """
            diccionario de las secciones,subsecciones y unidades ordenados + max
             de unidades
        """
        materia = cache.get("eol_completion-"+course_id+"-materia")
        max_unit =  cache.get("eol_completion-"+course_id+"-max_unit")
        if materia is None and max_unit is None: 
            materia, max_unit = self.get_materia(info, id_curso)
            cache.set("eol_completion-"+course_id+"-materia", materia, 300)
            cache.set("eol_completion-"+course_id+"-max_unit", max_unit, 300)
        """ 
            diccionario de los estudiantes con true/false si completaron las
            unidades
        """
        user_tick = cache.get("eol_completion-"+course_id+"-user_tick")
        if user_tick is None:            
            user_tick = self.get_ticks(
                materia, info, enrolled_students, course_key, max_unit)
            cache.set("eol_completion-"+course_id+"-user_tick", user_tick, 300)

        time = cache.get("eol_completion-"+course_id+"-time")
        if time is None:            
            time = datetime.now()
            time = time.strftime("%m/%d/%Y, %H:%M:%S")
            cache.set("eol_completion-"+course_id+"-time", time, 300)

        context = {
            "course": course,
            "lista_tick": user_tick,
            "materia": materia,
            "max": max_unit,
            "time": time
        }
        
        return context

    def get_materia(self, info, id_curso):
        """
            retorna diccionario de las secciones,subsecciones y unidades ordenados
        """
        max_unit = 0   # numero de unidades en todas las secciones
        materia = OrderedDict()
        curso_hijos = info[id_curso]
        curso_hijos = curso_hijos['children']  # todas las secciones del curso
        hijos = 0  # numero de unidades por seccion
        for id_seccion in curso_hijos:  # recorre cada seccion
            seccion = info[id_seccion]
            aux_name_sec = seccion['metadata']
            hijos = 0
            materia[id_seccion] = {
                'tipo': 'seccion',
                'nombre': aux_name_sec['display_name'],
                'id': id_seccion,
                'nhijos': hijos}
            subsecciones = seccion['children']
            for id_subseccion in subsecciones:  # recorre cada subseccion
                subseccion = info[id_subseccion]
                unidades = subseccion['children']
                aux_name = subseccion['metadata']
                hijos += len(unidades)
                materia[id_subseccion] = {
                    'tipo': 'subseccion',
                    'nombre': aux_name['display_name'],
                    'id': id_subseccion,
                    'nhijos': len(unidades)}
                for id_uni in unidades:  # recorre cada unidad y obtiene el nombre de esta
                    max_unit += 1
                    unidad = info[id_uni]
                    materia[id_uni] = {
                        'tipo': 'unidad',
                        'nombre': unidad['metadata']['display_name'],
                        'id': id_uni}
            materia[id_seccion] = {
                'tipo': 'seccion',
                'nombre': aux_name_sec['display_name'],
                'id': id_seccion,
                'nhijos': hijos}

        return materia, max_unit

    def get_ticks(
            self,
            materia,
            info,
            enrolled_students,
            course_key,
            max_unit):
        """
            diccionario los estudiantes con true/false si completaron las
            unidades
        """
        user_tick = OrderedDict()

        for user in enrolled_students:  # recorre cada estudiante
            certificado = self.get_certificate(user['id'], course_key)

            blocks = BlockCompletion.objects.filter(
                user=user['id'], course_key=course_key)
            # obtiene una lista con true/false si completaron las
            # unidades mas el numero de unidades completadas
            data = self.get_data_tick(materia, info, user, blocks, max_unit)

            user_tick[user['id']] = {'user': user['id'],
                                     'username': user['username'],
                                     'email': user['email'],
                                     'certificado': certificado,
                                     'data': data}
        return user_tick

    def get_data_tick(self, materia, info, user, blocks, max_unit):
        """
            obtiene una lista con true/false si completaron las unidades mas el
            numero de unidades completadas
        """
        data = []
        completed_unit = 0  # numero de unidades completadas por estudiante
        completed_unit_per_section = 0  # numero de unidades completadas por seccion
        num_units_section = 0  # numero de unidades por seccion
        first = True
        for unit in materia.items():
            if unit[1]['tipo'] == 'unidad':
                unit_info = info[unit[1]['id']]
                # bloques de la unidad
                blocks_unit = unit_info['children']
                verificador = self.get_block_tick(blocks_unit, blocks)
                completed_unit_per_section += 1
                num_units_section += 1
                completed_unit += 1
                data.append(verificador)
                if not verificador:
                    completed_unit -= 1
                    completed_unit_per_section -= 1

            if not first and unit[1]['tipo'] == 'seccion' and unit[1]['nhijos'] > 0:
                aux_point = str(completed_unit_per_section) + \
                    "/" + str(num_units_section)
                data.append(aux_point)
                completed_unit_per_section = 0
                num_units_section = 0
            if first and unit[1]['tipo'] == 'seccion' and unit[1]['nhijos'] > 0:
                first = False
        aux_point = str(completed_unit_per_section) + \
            "/" + str(num_units_section)
        data.append(aux_point)
        aux_final_point = str(completed_unit) + "/" + str(max_unit)
        data.append(aux_final_point)
        return data

    def get_block_tick(sefl, blocks_unit, blocks):
        """
            verifica si el bloque de la unidad fue completado
        """
        verificador = True
        i = 0
        while verificador and i < len(blocks_unit):  # recorre cada bloque
            bloque = blocks_unit[i]
            dicussion_block = bloque.split('@')
            # entra solo si el bloque no es discusion
            if dicussion_block[1] != 'discussion+block':
                usage_key = UsageKey.from_string(bloque)
                aux_block = blocks.filter(
                    block_key=usage_key).values('completion')
                # si el bloque no ha sido visto o no ha sido
                # completado
                if aux_block.count() == 0 or aux_block[0] == 0.0:
                    verificador = False
            i += 1
        return verificador
    
    def get_certificate(self, user_id, course_id):
        """
            verifica si el usuario tiene generado un certificado
        """
        certificado = GeneratedCertificate.certificate_for_student(
            user_id, course_id)
        if certificado is None:
            return 'No'
        return 'Si'
    
    def dump_module(
            self,
            module,
            destination=None,
            inherited=False,
            defaults=False):        
        """
        Add the module and all its children to the destination dictionary in
        as a flat structure.
        """

        destination = destination if destination else {}

        items = own_metadata(module)

        # HACK: add discussion ids to list of items to export (AN-6696)
        if isinstance(
                module,
                DiscussionXBlock) and 'discussion_id' not in items:
            items['discussion_id'] = module.discussion_id

        filtered_metadata = {
            k: v for k,
            v in six.iteritems(items) if k not in FILTER_LIST}

        destination[six.text_type(module.location)] = {
            'category': module.location.block_type,
            'children': [six.text_type(child) for child in getattr(module, 'children', [])],
            'metadata': filtered_metadata,
        }

        if inherited:
            # When calculating inherited metadata, don't include existing
            # locally-defined metadata
            inherited_metadata_filter_list = list(filtered_metadata.keys())
            inherited_metadata_filter_list.extend(INHERITED_FILTER_LIST)

            def is_inherited(field):
                if field.name in inherited_metadata_filter_list:
                    return False
                elif field.scope != Scope.settings:
                    return False
                elif defaults:
                    return True
                else:
                    return field.values != field.default

            inherited_metadata = {field.name: field.read_json(
                module) for field in module.fields.values() if is_inherited(field)}
            destination[six.text_type(
                module.location)]['inherited_metadata'] = inherited_metadata

        for child in module.get_children():
            self.dump_module(child, destination, inherited, defaults)

        return destination
