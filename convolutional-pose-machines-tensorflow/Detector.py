import numpy as np
import os
import six.moves.urllib as urllib
import sys
import tarfile
import tensorflow as tf
import zipfile

from collections import defaultdict
from io import StringIO
#from matplotlib import pyplot as plt
from PIL import Image


tensorflow_path = "/home/qiaohe/models"
sys.path.append(os.getcwd())
sys.path.append(tensorflow_path + "/research")
sys.path.append(tensorflow_path + "/research/object_detection")
sys.path.append(tensorflow_path + "/research/object_detection/utils")



#from models.research.object_detection.utils import ops as utils_ops
#from models.research.object_detection.utils import label_map_util
#from models.research.object_detection.utils import visualization_utils as vis_util
from utils import ops as utils_ops
from utils import label_map_util
from utils import visualization_utils as vis_util
#%matplotlib inline

PATH_TO_CKPT = 'models/research/object_detection/hand_inference_graph/frozen_inference_graph.pb'
PATH_TO_LABELS = 'models/research/object_detection/hand_inference_graph/hand_label_map.pbtxt'
NUM_CLASSES = 1

def load_image_into_numpy_array(image):
  (im_width, im_height) = image.size
  return np.array(image.getdata()).reshape((im_height, im_width, 3)).astype(np.uint8)

def run_inference_for_single_image(image, graph):
  with graph.as_default():
    with tf.Session() as sess:
      # Get handles to input and output tensors
      ops = tf.get_default_graph().get_operations()
      all_tensor_names = {output.name for op in ops for output in op.outputs}
      tensor_dict = {}
      for key in [
          'num_detections', 'detection_boxes', 'detection_scores',
          'detection_classes', 'detection_masks'
      ]:
        tensor_name = key + ':0'
        if tensor_name in all_tensor_names:
          tensor_dict[key] = tf.get_default_graph().get_tensor_by_name(
              tensor_name)
      if 'detection_masks' in tensor_dict:
        # The following processing is only for single image
        detection_boxes = tf.squeeze(tensor_dict['detection_boxes'], [0])
        detection_masks = tf.squeeze(tensor_dict['detection_masks'], [0])
        # Reframe is required to translate mask from box coordinates to image coordinates and fit the image size.
        real_num_detection = tf.cast(tensor_dict['num_detections'][0], tf.int32)
        detection_boxes = tf.slice(detection_boxes, [0, 0], [real_num_detection, -1])
        detection_masks = tf.slice(detection_masks, [0, 0, 0], [real_num_detection, -1, -1])
        detection_masks_reframed = utils_ops.reframe_box_masks_to_image_masks(
            detection_masks, detection_boxes, image.shape[0], image.shape[1])
        detection_masks_reframed = tf.cast(
            tf.greater(detection_masks_reframed, 0.5), tf.uint8)
        # Follow the convention by adding back the batch dimension
        tensor_dict['detection_masks'] = tf.expand_dims(
            detection_masks_reframed, 0)
      image_tensor = tf.get_default_graph().get_tensor_by_name('image_tensor:0')

      # Run inference
      output_dict = sess.run(tensor_dict,
                             feed_dict={image_tensor: np.expand_dims(image, 0)})

      # all outputs are float32 numpy arrays, so convert types as appropriate
      output_dict['num_detections'] = int(output_dict['num_detections'][0])
      output_dict['detection_classes'] = output_dict[
          'detection_classes'][0].astype(np.uint8)
      output_dict['detection_boxes'] = output_dict['detection_boxes'][0]
      output_dict['detection_scores'] = output_dict['detection_scores'][0]
      if 'detection_masks' in output_dict:
        output_dict['detection_masks'] = output_dict['detection_masks'][0]
  return output_dict

#PATH_TO_TEST_IMAGES_DIR = 'models/research/object_detection/test_images'
def bounding_box_from_folder(PATH_TO_TEST_IMAGES_DIR):
    #load frozen model into memory
    detection_graph = tf.Graph()
    with detection_graph.as_default():
      od_graph_def = tf.GraphDef()
      with tf.gfile.GFile(PATH_TO_CKPT, 'rb') as fid:
        serialized_graph = fid.read()
        od_graph_def.ParseFromString(serialized_graph)
        tf.import_graph_def(od_graph_def, name='')

    label_map = label_map_util.load_labelmap(PATH_TO_LABELS)
    categories = label_map_util.convert_label_map_to_categories(label_map, max_num_classes=NUM_CLASSES, use_display_name=True)
    category_index = label_map_util.create_category_index(categories)

    #image path

    TEST_IMAGE_PATHS = [ os.path.join(PATH_TO_TEST_IMAGES_DIR, 'image{}.jpg'.format(i)) for i in range(1, 19) ]
    IMAGE_SIZE = (12, 8)

    bounding_box = {}
    # this section finds one/two bound(s) according to xmin, ymin, xmax, ymax
    for index, image_path in enumerate(TEST_IMAGE_PATHS):
        image = Image.open(image_path)
        # the array based representation of the image will be used later in order to prepare the
        # result image with boxes and labels on it.
        image_np = load_image_into_numpy_array(image)
        height, width, _ = image_np.shape
        # Expand dimensions since the model expects images to have shape: [1, None, None, 3]
        image_np_expanded = np.expand_dims(image_np, axis=0)
        # Actual detection.
        output_dict = run_inference_for_single_image(image_np, detection_graph)
        # Visualization of the results of a detection.
        tmp = output_dict['detection_boxes'][::-1]

        predict_list = []
        if len(output_dict['detection_boxes']) >= 1 and output_dict['detection_scores'][0] > 0.5:
            output = output_dict['detection_boxes'][0,:]
            predict_list.append([output[1] * width, output[0] * height, output[3] * width, output[2] * height])

            if len(output_dict['detection_boxes']) >= 2 and output_dict['detection_scores'][1] > 0.5:
                output = output_dict['detection_boxes'][1,:]
                predict_list.append([output[1] * width, output[0] * height, output[3] * width, output[2] * height])
        #print(predict_list)
        bounding_box[index] = predict_list
    return bounding_box


print(bounding_box_from_folder('models/research/object_detection/test_images'))