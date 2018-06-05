import tensorflow as tf
import numpy as np
import cv2
import os
import importlib
import time
from config import FLAGS
import Ensemble_data_generator
from models.nets import cpm_model
# from models.nets import cpm_hand
import Detector as dt

def display_training_stats(step, lr, stage_losses, total_loss, lapse_time):
    lapse_time = time.time() - lapse_time
    status = 'Step: {}/{} ----- Cur_lr: {:1.7f} ----- Time: {:>2.2f} sec.'.format(step, FLAGS.training_iters,
                                                                                 lr, lapse_time)
    losses = ' | '.join(
        ['S{} loss: {:>7.2f}'.format(stage_num + 1, stage_losses[stage_num]) for stage_num in range(FLAGS.total_stages)])

    losses += ' | Total loss: {}'.format(total_loss)
    print(status)
    print(losses + '\n')
    
    
# GPU setting and environment

os.environ['CUDA_VISIBLE_DEVICES'] = '0'

model_path_suffix = os.path.join(#FLAGS.network_def,
                                 #'input_{}_output_{}'.format(FLAGS.input_size, FLAGS.heatmap_size),
                                 #'joints_{}'.format(FLAGS.num_of_joints),
                                 'stages_{}'.format(FLAGS.total_stages),
                                 'init_{}_rate_{}_step_{}'.format(FLAGS.lr, FLAGS.l_decay_rate,
                                                                  FLAGS.l_decay_step)
                                 )
model_dir = os.path.join('models',
                              'weights',
                              model_path_suffix)
# train_log_dir = os.path.join('models',
#                                   'logs',
#                                   model_path_suffix,
#                                   'train')
# test_log_dir = os.path.join('models',
#                                  'logs',
#                                  model_path_suffix,
#                                  'test')
os.system('mkdir -p {}'.format(model_dir))
# os.system('mkdir -p {}'.format(train_log_dir))
# os.system('mkdir -p {}'.format(test_log_dir))

train_itr = Ensemble_data_generator.ensemble_data_generator(FLAGS.train_tf_file, FLAGS.batch_size, FLAGS.image_size, FLAGS.box_size)
val_itr = Ensemble_data_generator.ensemble_data_generator(FLAGS.val_tf_file, FLAGS.batch_size, FLAGS.image_size, FLAGS.box_size)

# build the model
model = cpm_model.CPM_Model()
# model = cpm_hand.CPM_Model(input_size=FLAGS.image_size,
#                             heatmap_size=FLAGS.hmap_size,
#                             stages=FLAGS.total_stages,
#                             joints=FLAGS.total_joints,
#                             img_type=FLAGS.color_channel,
#                             #is_training=True
#                           )


# model.build_loss(FLAGS.lr, FLAGS.l_decay_rate, FLAGS.l_decay_step, FLAGS.optimizer)
print('============Model Build============\n')

# Here comes training
device_count = {'GPU': 1} if FLAGS.use_gpu else {'GPU': 0}

sess = tf.Session(config=tf.ConfigProto(device_count=device_count,
                                      allow_soft_placement=True))
# Prepare saver for check points
saver = tf.train.Saver(max_to_keep=0)

# Initial and run all varaibles
sess.run(tf.global_variables_initializer())

# Load model, if already have one
if FLAGS.pretrained_model != '':
#     for var in tf.trainable_variables():
#         with tf.variable_scope('', reuse=True):
#             var.initializer.run(session=sess)
    saver.restore(sess, os.path.join(model_dir, FLAGS.pretrained_model))
    
    # show the hyperparamters
    for var in tf.trainable_variables():
        with tf.variable_scope('', reuse=True):
            v = tf.get_variable(var.name[:-2])
            print(var.name, np.mean(sess.run(v)))
            
# Training iteration starts:
next_ele = train_itr.next()
for _ in range(FLAGS.training_iters):
    # time records 
    t0 = time.time()
    
    # get data and label from generator
    #batch_img, batch_joints = train_itr.next()
    
    #batch_img, batch_joints = sess.run([batch_img, batch_joints])
    batch_img, batch_joints = sess.run(next_ele)
    
    # normalize 
    batch_img = batch_img / 255 - 0.5
        
    # express label in the form of a heatmap
    batch_heatmap = dt.transform_joints_to_heatmap(FLAGS.image_size, FLAGS.hmap_size,
                                                        FLAGS.joint_gaussian_variance,
                                                        batch_joints)
    
    
    # go forward one step and prepare record
#     stage_loss, total_loss, op, cur_lr, stage_heatmap, global_step = sess.run([model.stage_loss, # loss of each stage
#               model.total_loss, # sum loss of all stages
#               model.train_op, # optimization, this must be done, otherwise the global step will not increment
#               #summary,# summary
#               model.cur_lr, # depreciating
#               model.stage_heatmap, # heatmaps of each stage
#               model.global_step # count steps
#               ],feed_dict={model.input_images: batch_img, model.gt_hmap_placeholder: batch_heatmap})
    stage_loss, total_loss, op, cur_lr, stage_heatmap, global_step = sess.run([model.stage_loss, # loss of each stage
              model.total_loss_train, # sum loss of all stages
              model.train_op, # optimization, this must be done, otherwise the global step will not increment
              #summary,# summary
              model.new_lr, # depreciating
              model.stage_maps, # heatmaps of each stage
              model.global_step # count steps
              ],feed_dict={model.images: batch_img, model.true_hmap_placeholder: batch_heatmap})
    
    # display record
    display_training_stats(global_step, cur_lr, stage_loss, total_loss, t0)
    
    # store train summary
    #train_log.add_summary(summaries, global_step)
    
    # intermediate results for debugging
    # todo: after prediction is changed to python file ,import its predict_image, and show intermediate image result
#     if (global_step + 1) % FLAGS.intermediate_showing == 0:
#         if FLAGS.normalize_img:
#             demo = batch_img[0] + 0.5
#         else:
#             demo = (batch_img[0] + 128.0) / 255

    # validates every some iterations
    if (global_step + 1) % FLAGS.validation_iters == 0:
        mean_loss = 0
        for i in range(FLAGS.validation_batch_per_iter):
            batch_img_test, batch_joints_test = val_itr.next()
            batch_img_test, batch_joints_test = sess.run([batch_img_test, batch_joints_test])
            
            # express label in the form of a heatmap
            batch_heatmap_test = dt.transform_joints_to_heatmap(FLAGS.image_size,
                                                                     FLAGS.hmap_size,
                                                                     FLAGS.joint_gaussian_variance,
                                                                     batch_joints_test)
            
            
            # go forward one step and prepare record
#             total_loss_test = sess.run(model.total_loss # sum loss of all stages
#                                               #summary,# summary
#                                              , feed_dict={model.input_images: batch_img_test,
#                                                                    model.gt_hmap_placeholder: batch_heatmap_test})
            total_loss_test = sess.run(model.total_loss_train # sum loss of all stages
                                              #summary,# summary
                                             , feed_dict={model.images: batch_img_test,
                                                                   model.true_hmap_placeholder: batch_heatmap_test})

            mean_loss += total_loss_test
        print('\nValidation loss: {:>7.2f}\n'.format(mean_loss / FLAGS.validation_batch_per_iter))
        #test_log.add_summary(summaries_test, global_step)
    
    # save model
    if (global_step + 1) % FLAGS.model_save_iters == 0:
        saver.save(sess=sess, save_path=os.path.join(model_dir, FLAGS.network_def),
                   global_step=(global_step + 1))
        print('\nModel checkpoint has been saved for {:d} steps\n'.format(global_step + 1))
    
    # end training
    if global_step == FLAGS.training_iters:
        print('\n{:d} steps have been finished, training ends\n'.format(global_step))
        break
sess.close() 