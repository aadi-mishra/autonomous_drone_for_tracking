import imgaug as ia
from imgaug import augmenters as iaa
import numpy as np
import xml.etree.ElementTree as ET

from PIL import Image

import tensorflow as tf
from object_detection.utils import dataset_util

flags = tf.app.flags
flags.DEFINE_string('output_path', '', 'Path to output TFRecord')
FLAGS = flags.FLAGS


def create_tf_example(image, bbox, im_shape):

    encoded_image_data = None
    with tf.gfile.GFile(image, 'rb') as fid:
        encoded_image_data = fid.read()  # Encoded image bytes

    height       = im_shape[1] # Image height
    width        = im_shape[0] # Image width
    filename     = image # Filename of the image. Empty if image is not from file
    image_format = b'png'

    xmins = [bbox[0]] # List of normalized left x coordinates in bounding box (1 per box)
    xmaxs = [bbox[1]] # List of normalized right x coordinates in bounding box (1 per box)
    ymins = [bbox[2]] # List of normalized top y coordinates in bounding box (1 per box)
    ymaxs = [bbox[3]] # List of normalized bottom y coordinates in bounding box (1 per box)

    classes      = [1] # List of integer class id of bounding box (1 per box)
    classes_text = ['car'] # List of string class name of bounding box (1 per box)


    tf_example = tf.train.Example(features=tf.train.Features(feature={
            'image/height': dataset_util.int64_feature(height),
            'image/width': dataset_util.int64_feature(width),
            'image/filename': dataset_util.bytes_feature(filename),
            'image/source_id': dataset_util.bytes_feature(filename),
            'image/encoded': dataset_util.bytes_feature(encoded_image_data),
            'image/format': dataset_util.bytes_feature(image_format),
            'image/object/bbox/xmin': dataset_util.float_list_feature(xmins),
            'image/object/bbox/xmax': dataset_util.float_list_feature(xmaxs),
            'image/object/bbox/ymin': dataset_util.float_list_feature(ymins),
            'image/object/bbox/ymax': dataset_util.float_list_feature(ymaxs),
            'image/object/class/text': dataset_util.bytes_list_feature(classes_text),
            'image/object/class/label': dataset_util.int64_list_feature(classes),
    }))
    return tf_example


def main(_):
    writer = tf.python_io.TFRecordWriter(FLAGS.output_path)

    seq = iaa.Sequential(
    [
        iaa.Fliplr(0.5), # horizontally flip 50% of all images
        iaa.Flipud(0.2), # vertically flip 20% of all images
        # crop images by -10% to 20% of their height/width
        sometimes(iaa.CropAndPad(
            percent=(-0.1, 0.2),
            pad_mode=ia.ALL,
            pad_cval=(0, 255)
        )),
        sometimes(iaa.Affine(
            translate_percent={"x": (-0.5, 0.5), "y": (-0.5, 0.5)}, # translate by -50 to +50 percent (per axis)
            rotate=(-90, 90), # rotate by -90 to +90 degrees
            order=[0, 1], # use nearest neighbour or bilinear interpolation (fast)
            cval=(0, 255), # if mode is constant, use a cval between 0 and 255
            mode=ia.ALL # use any of scikit-image's warping modes (see 2nd image from the top for examples)
        )),
    ],
    random_order=True)

    ann              = None
    num_orig_samples = 10
    num_batches      = 1000
    images, bboxs    = [], []

    for i in range num_orig_samples:
        path = 'data/orig_data/' + str(i) + '.xml'
        tree = ET.parse(path)
        root = tree.getroot()

        obj = root.findall('object')
        bndbox = obj.find('bndbox')

        xmin = int(bndbox.find('xmin').text)
        xmax = int(bndbox.find('xmax').text)
        ymin = int(bndbox.find('ymin').text)
        ymax = int(bndbox.find('ymax').text)

        image = np.asarray(Image.open('data/orig_data/' + str(i).zfill(2) + '.png'), dtype='uint8')
        bbox  = ia.BoundingBoxesOnImage([ia.BoundingBox(x1=xmin, y1=ymin, x2=xmax, y2=ymax)], shape=image.shape)

        images.append(image)
        bboxs.append(bbox)

    for i in range(num_batches):
        seq_det    = seq.to_deterministic()
        aug_images = seq_det.augment_images(images)
        aug_bboxs  = seq_det.augment_bounding_boxes(bboxs)

        for j, (image, bbox) in enumerate(zip(aug_images, aug_bboxs)):

            result   = Image.fromarray(image)
            out_path = 'data/' + str(i*num_orig_samples+j).zfill(5) + '.png'
            result.save(out_path)

            print bbox
            # bbox = ...

            tf_example = create_tf_example(out_path, bbox, image.shape)
            writer.write(tf_example.SerializeToString())

    writer.close()


if __name__ == '__main__':
  tf.app.run()