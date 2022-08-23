import glob
import os
from skywinder.communication import file_format_classes


def sort_and_write(input_dir, output_base_dir):
    for fn in glob.glob(input_dir):
        myfile = file_format_classes.GeneralFile.from_file(fn)
        out_fn = os.path.join(output_base_dir, str(myfile.camera_id), myfile.filename)
        myfile.write_payload_to_file(out_fn)
