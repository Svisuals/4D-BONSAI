# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2021 Dion Moult <dion@thinkmoult.com>, 2022 Yassine Oualid <yassine@sigmadimensions.com>, 2025 Federico Eraso <feraso@svisuals.net>
#
# This file is part of Bonsai.	
#
# Bonsai is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Bonsai is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Bonsai.  If not, see <http://www.gnu.org/licenses/>.


import bonsai.tool as tool

class TaskICOMData:
    data = {}
    is_loaded = False

    @classmethod
    def load(cls):
        cls.data = {"can_active_resource_be_assigned": cls.can_active_resource_be_assigned()}
        cls.is_loaded = True

    @classmethod
    def can_active_resource_be_assigned(cls) -> bool:
        props = tool.Resource.get_resource_props()
        active_resource = props.active_resource
        if active_resource:
            resource_id = active_resource.ifc_definition_id
            return not tool.Ifc.get().by_id(resource_id).is_a("IfcCrewResource")
        return False