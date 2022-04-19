import sys
from pmc_turbo.camera.image_processing import blosc_file
from pmc_turbo.camera.image_processing import jpeg


def make_jpeg_from_blosc(input_filename, output_filename, **kwargs):
    img, chunk = blosc_file.load_blosc_image(input_filename)
    img_jpeg, offset, scale = jpeg.simple_jpeg(img, **kwargs)
    image_name = input_filename.split('/')[-1]
    with open(output_filename, 'wb') as f:
        f.write(img_jpeg)


# if __name__ == "__main__":
#     print sys.argv()
#     input_filename = sys.argv()[1]
#     output_filename = sys.argv()[2]
#     make_jpeg_from_blosc(input_filename, output_filename)
