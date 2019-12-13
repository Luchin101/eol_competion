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

"""
def my_custom_function(request, course_id):
    course_key = CourseKey.from_string(course_id)
    course = get_course_with_access(request.user, "load", course_key)

    context = {
        "course": course,
    }
    return render_to_response("eol_completion/eol_completion_fragment.html", context)

"""
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
        user_tick, max_u = self.get_ticks(materia, info, enrolled_students, course_key)#diccionario los estudiantes con true/false si completaron las unidades + ptos

        context = {
            "course": course,
            "lista_alumnos": enrolled_students,
            "lista_tick": user_tick,
            "materia": materia,
            "max": max_u,
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
            aux=OrderedDict()
            for id_subseccion in subsecciones:#recorre cada subseccion
                subseccion = info[id_subseccion]
                unidades = subseccion['children']
                aux_name = subseccion['metadata']
                hijos += len(unidades)
                aux22=OrderedDict()
                for id_uni in unidades: # recorre cada unidad y obtiene el nombre de esta
                    unidad = info[id_uni]
                    uni_name = unidad['metadata']['display_name']
                    aux22[id_uni] = {'name_uni': uni_name, 'id': id_uni }
                aux[id_subseccion] = {'name_sub': aux_name['display_name'], 'children_sub': aux22, 'id':id_subseccion, 'total_hijos': len(unidades)}

            aux_name2 = seccion['metadata']
            materia[id_seccion] = {'name_seccion': aux_name2['display_name'], 'children_seccion': aux, 'id':id_seccion, 'total_hijos': hijos}
        return materia

    def get_ticks(self, materia, info, enrolled_students, course_key):
        user_tick = OrderedDict()
        max_u = 0   # numero de unidades en todas las secciones    
        contar = True
        #arreglo_tick = [] // en vez de usar diccionario para almacenar los true/false si los estudiantes completaron las unidades
        k=0
        for user in enrolled_students: #recorre cada estudiante
            blocks = BlockCompletion.objects.filter(user=user['id'], course_key=course_key)
            uaux3=OrderedDict()
            com_u = 0 #numero de unidades completadas por estudiante
            
            #arreglo_tick.append([])
            #arreglo_tick.append(user['username'])
            for u_sec in materia: #recorre cada seccion                
                aux2 = materia[u_sec]['children_seccion']
                uaux= OrderedDict()
                psec=0#numero de unidades completadas por seccion
                maxsec=0#numero de unidades por seccion
                #recorre cada subseccion
                for u_sub in aux2.items(): #list(my_dict.items())[0]  in python 3.x 
                    aux3 = u_sub[1]['children_sub']
                    uaux2=OrderedDict()
                    for u_uni in aux3:#recorre cada unidad
                        aux4 = info[u_uni]
                        u_block = aux4['children'] #bloques de la unidad
                        bul = True 
                        if contar:
                            max_u += 1
                        psec += 1
                        maxsec += 1
                        com_u += 1                      
                        for bloque in u_block: #recorre cada bloque 
                            usage_key = UsageKey.from_string(bloque)
                            aux5 = blocks.filter(block_key=usage_key).values('completion')                            
                            if aux5.count() == 0 or aux5[0] == 0.0: #si el bloque no ha sido visto o no ha sido completado                               
                                bul=False
                        if not bul:
                            com_u -= 1
                            psec -= 1
                        uaux2[u_uni] = [u_uni, bul, aux4['metadata']['display_name']]
                        #arreglo_tick[k].append(bul)
                    uaux[u_sub[0]] = {'subseccion':u_sub[0], 'unidades': uaux2}
                #arreglo_tick[k].append(psec+"/"+maxsec)
                uaux3[u_sec] = {'seccion': u_sec, 'subs':uaux, 'ptos': psec, 'max': maxsec}
            user_tick[user['id']] = {'user': user['id'], 'sec':uaux3, 'ptos': com_u}
            contar = False
            #arreglo_tick[k].append(com_u+"/"+max_u)
            k += 1
        return user_tick, max_u

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