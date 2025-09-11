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


def save_ColorTypes_to_ifc_core(ifc_file: "ifcopenshell.file", work_schedule: "ifcopenshell.entity_instance", ColorType_data: dict) -> None:
    """
    (Core) Saves 4D ColorTypes configuration to an IfcPropertySet associated with the active IfcWorkSchedule.
    """
    import json
    import ifcopenshell.api
    from datetime import datetime

    pset_name = "Pset_Bonsai4DColorTypeConfig"
    prop_name = "ColorTypeDataJSON"

    # 1. Serialize all configuration to a JSON string
    ColorType_json = json.dumps(ColorType_data, ensure_ascii=False, indent=2)

    # 2. Create properties that will go in the Pset
    try:
        properties_to_add = {
            prop_name: ifc_file.create_entity(
                "IfcPropertySingleValue",
                Name=prop_name,
                NominalValue=ifc_file.create_entity("IfcText", ColorType_json),
            ),
            "Version": ifc_file.create_entity(
                "IfcPropertySingleValue",
                Name="Version",
                NominalValue=ifc_file.create_entity("IfcLabel", "1.0"),
            ),
            "LastModified": ifc_file.create_entity(
                "IfcPropertySingleValue",
                Name="LastModified",
                NominalValue=ifc_file.create_entity("IfcText", datetime.now().isoformat()),
            ),
        }

        # 3. Use ifcopenshell API to create or edit Pset robustly
        ifcopenshell.api.run(
            "pset.edit_pset",
            ifc_file,
            product=work_schedule,
            name=pset_name,
            properties=properties_to_add,
        )
    except Exception:
        # Robust fallback: use simple values instead of entities
        ifcopenshell.api.run(
            "pset.edit_pset",
            ifc_file,
            product=work_schedule,
            name=pset_name,
            properties={
                prop_name: ColorType_json,
                "Version": "1.0",
                "LastModified": datetime.now().isoformat(),
            },
        )
    print(f"Bonsai INFO: 4D ColorTypes automatically saved to WorkSchedule Pset '{pset_name}'.")


    def load_ColorTypes_from_ifc_core(work_schedule: "ifcopenshell.entity_instance") -> dict | None:
        """(Core) Loads 4D ColorTypes configuration from the IfcPropertySet associated with the IfcWorkSchedule. """
        import json

        pset_name = "Pset_Bonsai4DColorTypeConfig"
        prop_name = "ColorTypeDataJSON"

        if not getattr(work_schedule, "IsDefinedBy", None):
            return None

        for rel in work_schedule.IsDefinedBy:
            # Ensure the relationship is for properties
            if not rel.is_a("IfcRelDefinesByProperties"):
                continue

            pset = rel.RelatingPropertySet
            if getattr(pset, "Name", None) == pset_name:
                for prop in getattr(pset, "HasProperties", []) or []:
                    if getattr(prop, "Name", None) == prop_name and prop.is_a("IfcPropertySingleValue"):
                        try:
                            nominal = getattr(prop, "NominalValue", None)
                            # Robust handling of the nominal value (wrappedValue or direct value)
                            if hasattr(nominal, "wrappedValue"):
                                raw = nominal.wrappedValue
                            else:
                                raw = nominal
                            data = json.loads(raw) if isinstance(raw, str) else None
                            if isinstance(data, dict):
                                print(f"Bonsai INFO: 4D ColorTypes loaded from IFC for WorkSchedule '{getattr(work_schedule, 'Name', '')}'.")
                                return data
                        except Exception as e:
                            print(f"Bonsai ERROR: Could not decode ColorTypes JSON from IFC: {e}")
                            return None
        return None
