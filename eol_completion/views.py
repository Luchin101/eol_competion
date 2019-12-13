# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import six
import json

from courseware.courses import get_course_with_access
from django.template.loader import render_to_string
from django.shortcuts import render_to_response
from web_fragments.fragment import Fragment

from openedx.core.djangoapps.plugin_api.views import EdxFragmentView

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
        
        html = render_to_string('eol_completion/eol_completion_fragment.html', context)
        fragment = Fragment(html)
        return fragment

    def get_context(self, request, course_id):
        course_key = CourseKey.from_string(course_id)
        course = get_course_with_access(request.user, "load", course_key)
        enrolled_students = User.objects.filter(
            courseenrollment__course_id=course_key,
            courseenrollment__is_active=1
        ).order_by('username').values('id', 'username')
        store = modulestore()
        info = self.dump_module(store.get_course(course_key))

        curso_aux=course_id.split(":", 1)
        id_curso = 'block-v1:'+curso_aux[1]+'+type@course+block@course'        
        materia = self.get_materia(info,id_curso)#diccionario de las secciones,subsecciones y unidades ordenados
        user_tick, max_unit = self.get_ticks(materia, info, enrolled_students, course_key)#diccionario los estudiantes con true/false si completaron las unidades + ptos

        context = {
            "course": course,
            "lista_alumnos": enrolled_students,
            "lista_tick": user_tick,
            "materia": materia,
            "max": max_unit,
            #"a_tick": arreglo_tick
        }
        return context
    
    def get_materia(self, info, id_curso):
        materia = OrderedDict()
        curso_hijos = info[id_curso]
        curso_hijos = curso_hijos['children'] #todas las secciones del curso
        hijos=0# numero de unidades por seccion
        for id_seccion in curso_hijos:#recorre cada seccion
            seccion = info[id_seccion]
            hijos=0
            subsecciones = seccion['children']
            aux_subsec_dict=OrderedDict()
            for id_subseccion in subsecciones:#recorre cada subseccion
                subseccion = info[id_subseccion]
                unidades = subseccion['children']
                aux_name = subseccion['metadata']
                hijos += len(unidades)
                unit_dict=OrderedDict()
                for id_uni in unidades: # recorre cada unidad y obtiene el nombre de esta
                    unidad = info[id_uni]
                    unit_name = unidad['metadata']['display_name']
                    unit_dict[id_uni] = {'name_uni': unit_name, 'id': id_uni }
                aux_subsec_dict[id_subseccion] = {'name_sub': aux_name['display_name'], 'children_sub': unit_dict, 'id':id_subseccion, 'total_hijos': len(unidades)}

            aux_name_sec = seccion['metadata']
            materia[id_seccion] = {'name_seccion': aux_name_sec['display_name'], 'children_seccion': aux_subsec_dict, 'id':id_seccion, 'total_hijos': hijos}
        return materia

    def get_ticks(self, materia, info, enrolled_students, course_key):
        user_tick = OrderedDict()
        max_unit = 0   # numero de unidades en todas las secciones    
        contar = True
        #arreglo_tick = [] // en vez de usar diccionario para almacenar los true/false si los estudiantes completaron las unidades
        #k=0
        for user in enrolled_students: #recorre cada estudiante
            blocks = BlockCompletion.objects.filter(user=user['id'], course_key=course_key)
            section_dict=OrderedDict()
            completed_unit = 0 #numero de unidades completadas por estudiante
            
            #arreglo_tick.append([])
            #arreglo_tick.append(user['username'])
            for section in materia: #recorre cada seccion                
                aux_section = materia[section]['children_seccion']
                subsection_dict= OrderedDict()
                completed_unit_per_section=0#numero de unidades completadas por seccion
                num_units_section=0#numero de unidades por seccion
                #recorre cada subseccion
                for aux_subsection in aux_section.items(): #list(my_dict.items())[0]  in python 3.x 
                    list_subsection = aux_subsection[1]['children_sub']
                    dict_unit=OrderedDict()
                    for id_unit in list_subsection:#recorre cada unidad
                        unit_info = info[id_unit]
                        blocks_unit = unit_info['children'] #bloques de la unidad
                        verificador = True 
                        if contar:
                            max_unit += 1
                        completed_unit_per_section += 1
                        num_units_section += 1
                        completed_unit += 1                      
                        for bloque in blocks_unit: #recorre cada bloque 
                            usage_key = UsageKey.from_string(bloque)
                            aux_block = blocks.filter(block_key=usage_key).values('completion')                            
                            if aux_block.count() == 0 or aux_block[0] == 0.0: #si el bloque no ha sido visto o no ha sido completado                               
                                verificador=False
                        if not verificador:
                            completed_unit -= 1
                            completed_unit_per_section -= 1
                        dict_unit[id_unit] = [id_unit, verificador, unit_info['metadata']['display_name']]
                        #arreglo_tick[k].append(verificador)
                    subsection_dict[aux_subsection[0]] = {'subseccion':aux_subsection[0], 'unidades': dict_unit}
                #arreglo_tick[k].append(completed_unit_per_section+"/"+num_units_section)
                section_dict[section] = {'seccion': section, 'subs':subsection_dict, 'ptos': completed_unit_per_section, 'max': num_units_section}
            user_tick[user['id']] = {'user': user['id'], 'sec':section_dict, 'ptos': completed_unit}
            contar = False
            #arreglo_tick[k].append(completed_unit+"/"+max_unit)
            #k += 1
        return user_tick, max_unit

    def dump_module(self, module, destination=None, inherited=False, defaults=False):
        """
        Add the module and all its children to the destination dictionary in
        as a flat structure.
        """

        destination = destination if destination else {}

        items = own_metadata(module)

        # HACK: add discussion ids to list of items to export (AN-6696)
        if isinstance(module, DiscussionXBlock) and 'discussion_id' not in items:
            items['discussion_id'] = module.discussion_id

        filtered_metadata = {k: v for k, v in six.iteritems(items) if k not in FILTER_LIST}

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

            inherited_metadata = {field.name: field.read_json(module) for field in module.fields.values() if is_inherited(field)}
            destination[six.text_type(module.location)]['inherited_metadata'] = inherited_metadata

        for child in module.get_children():
            self.dump_module(child, destination, inherited, defaults)

        return destination