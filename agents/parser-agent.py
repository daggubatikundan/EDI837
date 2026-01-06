import json
import sys
import glob
import os

class EDIParserAgent:
    def __init__(self, delimiter="*"):
        self.delimiter = delimiter
        self.segments = {}
        
    def parse_edi(self, edi_file_path):
        # reset state for each file parsed
        self.segments = {}

        with open(edi_file_path, 'r') as edi_file:
            edi_content = edi_file.read()

        # Split the content by the standard segment terminator (~)
        raw_segments = edi_content.split("~")

        for segment in raw_segments:
            # normalize and skip empty/blank segments
            segment = segment.strip()
            if not segment:
                continue

            # Each segment is usually in the form of "NM1*85*2*HOSPITAL..."
            segment_fields = segment.split(self.delimiter)
            # normalize segment id
            segment_id = segment_fields[0].strip()
            if not segment_id:
                continue

            if segment_id not in self.segments:
                self.segments[segment_id] = []

            # Map the fields to the segment's respective key-value pairs
            segment_data = self.map_segment_data(segment_id, segment_fields)

            # Append the parsed segment data
            self.segments[segment_id].append(segment_data)

        return self.segments

    def map_segment_data(self, segment_id, fields):
        # Here we will define how each segment is mapped. 
        # For example, for the NM1 segment, it might be:
        if segment_id == "NM1":
            return {
                "entity_identifier_code": fields[1],
                "entity_type_qualifier": fields[2],
                "name_last_or_organization": fields[3],
                "name_first": fields[4] if len(fields) > 4 else None,
                "name_middle": fields[5] if len(fields) > 5 else None,
            }
        elif segment_id == "ISA":
            return {
                "authorization_information_qualifier": fields[1],
                "authorization_information": fields[2],
                "security_information_qualifier": fields[3],
                "security_information": fields[4],
                "interchange_sender_id": fields[6],
                "interchange_receiver_id": fields[7],
                # Add more fields based on the ISA segment specification
            }
        elif segment_id == "GS":
            return {
                "functional_group_code": fields[1],
                "application_sender_code": fields[2],
                "application_receiver_code": fields[3],
                # Add more fields based on the GS segment specification
            }
        elif segment_id == "ST":
            return {
                "transaction_set_identifier_code": fields[1] if len(fields) > 1 else None,
                "transaction_set_control_number": fields[2] if len(fields) > 2 else None,
            }
        elif segment_id == "BHT":
            return {
                "hierarchical_structure_code": fields[1] if len(fields) > 1 else None,
                "transaction_set_purpose_code": fields[2] if len(fields) > 2 else None,
                "reference_identification": fields[3] if len(fields) > 3 else None,
                "date": fields[4] if len(fields) > 4 else None,
                "time": fields[5] if len(fields) > 5 else None,
                "transaction_type_code": fields[6] if len(fields) > 6 else None,
            }
        elif segment_id == "PER":
            return {
                "contact_function_code": fields[1] if len(fields) > 1 else None,
                "name": fields[2] if len(fields) > 2 else None,
                "comm_qual_1": fields[3] if len(fields) > 3 else None,
                "comm_number_1": fields[4] if len(fields) > 4 else None,
                "comm_qual_2": fields[5] if len(fields) > 5 else None,
                "comm_number_2": fields[6] if len(fields) > 6 else None,
            }
        elif segment_id == "HL":
            return {
                "hierarchical_id_number": fields[1] if len(fields) > 1 else None,
                "hierarchical_parent_id_number": fields[2] if len(fields) > 2 else None,
                "hierarchical_level_code": fields[3] if len(fields) > 3 else None,
                "hierarchical_child_code": fields[4] if len(fields) > 4 else None,
            }
        elif segment_id == "N3":
            return {
                "address_line_1": fields[1] if len(fields) > 1 else None,
                "address_line_2": fields[2] if len(fields) > 2 else None,
            }
        elif segment_id == "N4":
            return {
                "city": fields[1] if len(fields) > 1 else None,
                "state": fields[2] if len(fields) > 2 else None,
                "postal_code": fields[3] if len(fields) > 3 else None,
            }
        elif segment_id == "REF":
            return {
                "reference_id_qualifier": fields[1] if len(fields) > 1 else None,
                "reference_id": fields[2] if len(fields) > 2 else None,
            }
        elif segment_id == "SBR":
            return {
                "payer_relationship_code": fields[1] if len(fields) > 1 else None,
                "benefit_status_code": fields[2] if len(fields) > 2 else None,
                "insurance_type_code": fields[3] if len(fields) > 3 else None,
                "coordination_of_benefits": fields[4] if len(fields) > 4 else None,
                "group_number": fields[5] if len(fields) > 5 else None,
            }
        elif segment_id == "DMG":
            return {
                "date_time_qualifier": fields[1] if len(fields) > 1 else None,
                "birth_date": fields[2] if len(fields) > 2 else None,
                "gender": fields[3] if len(fields) > 3 else None,
            }
        elif segment_id == "CLM":
            return {
                "patient_control_number": fields[1] if len(fields) > 1 else None,
                "monetary_amount": fields[2] if len(fields) > 2 else None,
                "filling_indicator": fields[3] if len(fields) > 3 else None,
                "place_of_service": fields[4] if len(fields) > 4 else None,
                "facility_type_code": fields[5] if len(fields) > 5 else None,
            }
        elif segment_id == "HI":
            # HI often contains composite diagnosis/procedure codes; return raw and parsed where possible
            return {
                "hi_all": fields[1:] if len(fields) > 1 else [],
            }
        elif segment_id == "PRV":
            return {
                "provider_code": fields[1] if len(fields) > 1 else None,
                "provider_qualifier": fields[2] if len(fields) > 2 else None,
                "provider_value": fields[3] if len(fields) > 3 else None,
            }
        elif segment_id == "LX":
            return {
                "assigned_number": fields[1] if len(fields) > 1 else None,
            }
        elif segment_id == "SV1":
            # Service line with potentially colon-separated product/service id
            svc_id = fields[1] if len(fields) > 1 else None
            svc_parts = svc_id.split(":") if svc_id else []
            return {
                "composite_med_proc_id": svc_id,
                "composite_med_proc_id_parts": svc_parts,
                "charge_amount": fields[2] if len(fields) > 2 else None,
                "unit_measure": fields[3] if len(fields) > 3 else None,
                "service_unit_count": fields[4] if len(fields) > 4 else None,
            }
        elif segment_id == "DTP":
            return {
                "date_time_qualifier": fields[1] if len(fields) > 1 else None,
                "date_time_period_format_qualifier": fields[2] if len(fields) > 2 else None,
                "date_time_period": fields[3] if len(fields) > 3 else None,
            }
        elif segment_id == "SE":
            return {
                "number_of_included_segments": fields[1] if len(fields) > 1 else None,
                "transaction_set_control_number": fields[2] if len(fields) > 2 else None,
            }
        else:
            return {f"field_{i}": field for i, field in enumerate(fields)}

# Example usage
if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else 'agents/837-files/*.*'

    parser_agent = EDIParserAgent()
    all_results = {}

    # expand glob; if the pattern points to a real file, use it
    files = glob.glob(path)
    if not files and os.path.isfile(path):
        files = [path]

    for fp in files:
        try:
            parsed = parser_agent.parse_edi(fp)
            all_results[fp] = parsed
        except Exception as e:
            all_results[fp] = {"error": str(e)}

    print(json.dumps(all_results, indent=4))
