import astropy.io.fits
import astropy.wcs

import numpy as np
import pandas as pd

import matplotlib.pyplot as plt

import copy
import os
from torch.nn import functional as F
import proceesing
import label_caliculator
import ring_sub



def make_ring(spitzer_path, name, train_cfg):

    train_l = [
    'spitzer_02100+0000_rgb','spitzer_04200+0000_rgb','spitzer_33300+0000_rgb','spitzer_35400+0000_rgb',
    'spitzer_00300+0000_rgb','spitzer_02400+0000_rgb','spitzer_04500+0000_rgb','spitzer_31500+0000_rgb',
    'spitzer_33600+0000_rgb','spitzer_35700+0000_rgb','spitzer_00600+0000_rgb','spitzer_02700+0000_rgb',
    'spitzer_04800+0000_rgb','spitzer_29700+0000_rgb','spitzer_31800+0000_rgb','spitzer_03000+0000_rgb',
    'spitzer_05100+0000_rgb','spitzer_30000+0000_rgb','spitzer_32100+0000_rgb','spitzer_01200+0000_rgb',
    'spitzer_03300+0000_rgb','spitzer_05400+0000_rgb','spitzer_30300+0000_rgb','spitzer_32400+0000_rgb',
    'spitzer_34500+0000_rgb','spitzer_01500+0000_rgb','spitzer_03600+0000_rgb','spitzer_05700+0000_rgb',
    'spitzer_30600+0000_rgb','spitzer_32700+0000_rgb','spitzer_34800+0000_rgb','spitzer_01800+0000_rgb',
    'spitzer_06000+0000_rgb','spitzer_30900+0000_rgb','spitzer_33000+0000_rgb','spitzer_35100+0000_rgb']
    train_l = sorted(train_l)

    sig1 = 1/(2*(np.log(2))**(1/2))

    # choice catalogue from 'CH' or 'MWP'
    Ring_CATA = ring_sub.catalogue('MWP')

    frame_mwp_train = []
    mwp_ring_list_train = []

    l = train_l
    train_count = 0
    train_nan_count = 0

    for i in range(len(l)): 

        fits_path = l[i]
        spitzer_rfits = astropy.io.fits.open(spitzer_path+'/'+fits_path+'/'+'r.fits')[0]
        spitzer_gfits = astropy.io.fits.open(spitzer_path+'/'+fits_path+'/'+'g.fits')[0]
        spitzer_bfits = astropy.io.fits.open(spitzer_path+'/'+fits_path+'/'+'b.fits')[0]

        #RGBにしたいため、fitsのdataを重ねる
        data = np.concatenate([proceesing.remove_nan(spitzer_rfits.data[:,:,None]), 
                                proceesing.remove_nan(spitzer_gfits.data[:,:,None]), 
                                proceesing.remove_nan(spitzer_bfits.data[:,:,None])], axis=2)


        a = data.shape[0]
        b = data.shape[1]
#         data[data!=data] = 0
        w = astropy.wcs.WCS(spitzer_rfits.header)
        GLON_min, GLAT_min = w.all_pix2world(b, 0, 0)
        GLON_max, GLAT_max = w.all_pix2world(0, a, 0) 

        GLON_center = (GLON_min+GLON_max)/2
        GLON_new_min = GLON_center-1.5
        GLON_new_max = GLON_center+1.5
        
        Ring_cata = Ring_CATA.query('@GLON_new_min < GLON <= @GLON_new_max')
        Ring_cata = Ring_cata.reset_index()
        train_count += len(Ring_cata)

        # star_listは辞書
        star_dic = label_caliculator.all_star(Ring_cata, w)
        print(fits_path)

        for _, row in Ring_cata.iterrows():    

            flip = train_cfg['flip']
            rot = train_cfg['rotate']
            scale = train_cfg['scale']
            translation = train_cfg['translation']

            x_pix_min, y_pix_min, x_pix_max, y_pix_max, width, hight, flag = label_caliculator.calc_pix(row, w, 
                                                                                GLON_new_min, GLON_new_max,
                                                                                GLAT_min, GLAT_max, 'train', 1/0.89)


            if flag: #calc_pix時に100回試行してもできなかった場合の場合分け   
                cover_star_position, cover_star_name = label_caliculator.find_cover(star_dic, x_pix_min, y_pix_min, 
                                                                                    x_pix_max, y_pix_max)
                if x_pix_min<0 or y_pix_min<0:
                    pass

                else:
                    c_data = data[int(y_pix_min):int(y_pix_max), int(x_pix_min):int(x_pix_max)].view()
                    cut_data = copy.deepcopy(c_data)

                    if np.isnan(cut_data.sum()):
                        pass
                        
                    else:
                        pi = proceesing.conv(300, sig1, cut_data)
                        xmin_list, ymin_list, xmax_list, ymax_list, name_list = label_caliculator.make_label(x_pix_min, y_pix_min, x_pix_max, y_pix_max, 
                                                                                            cover_star_position, cover_star_name,
                                                                                            width, hight, Ring_CATA)
                        r_shape_y = pi.shape[0]
                        r_shape_x = pi.shape[1]
                        res_data = pi[int(r_shape_y/4):int(r_shape_y*3/4), int(r_shape_x/4):int(r_shape_x*3/4)]
                        res_data = proceesing.normalize(res_data)
                        res_data = proceesing.resize(res_data, 300)
                        xmin_list, ymin_list, xmax_list, ymax_list = label_caliculator.check_list(xmin_list, ymin_list, 
                                                                                                    xmax_list, ymax_list)
                            
                        info = {'fits':fits_path, 'name':name_list, 'xmin':xmin_list, 'xmax':xmax_list, 
                                'ymin':ymin_list, 'ymax':ymax_list}

                        def append_data(data, info, data_list, frame):
                            if not np.isnan(data.sum()):
                                data_list.append(data)
                                frame.append(info)

                        append_data(res_data, info, mwp_ring_list_train, frame_mwp_train)

                        if rot:
                            # deg = np.random.randint(0, 359)
                            for deg in [90, 180, 270, 360]:
                                res_data, rotate_cut_data, info = ring_sub.rotate_data(
                                    pi, deg, xmin_list, ymin_list, xmax_list, ymax_list, name_list, fits_path)
                                append_data(res_data, info, mwp_ring_list_train, frame_mwp_train)
                                
                                if flip:
                                    ud_res_data, lr_res_data = ring_sub.flip_data(rotate_cut_data)
                                    info = {'fits':fits_path, 'name':name_list, 'xmin':xmin_list, 'xmax':xmax_list, 
                                            'ymin':ymin_list, 'ymax':ymax_list}
                                    
                                    append_data(ud_res_data, info, mwp_ring_list_train, frame_mwp_train)
                                    append_data(lr_res_data, info, mwp_ring_list_train, frame_mwp_train)
                                    
                                    if type(scale) == bool:
                                        pass
                                    else:
                                        fl, scale_data, info = ring_sub.scale(row, w,GLON_new_min,GLON_new_max,
                                                                            GLAT_min, GLAT_max, scale, star_dic, 
                                                                            'train', Ring_CATA, data, fits_path)
                                        if fl:
                                            append_data(scale_data, info, mwp_ring_list_train, frame_mwp_train)

                                else:
                                    if type(scale) == bool:
                                        pass
                                    else:
                                        fl, scale_data, info = ring_sub.scale(row, w,GLON_new_min,GLON_new_max,
                                                                            GLAT_min, GLAT_max, scale, star_dic, 
                                                                            'train', Ring_CATA, data, fits_path)
                                        if fl:
                                            append_data(scale_data, info, mwp_ring_list_train, frame_mwp_train)

                                    
                        else:
                            if flip:
                                    
                                ud_res_data, lr_res_data = ring_sub.flip_data(pi)
                                append_data(ud_res_data, info, mwp_ring_list_train, frame_mwp_train)
                                append_data(lr_res_data, info, mwp_ring_list_train, frame_mwp_train)
                                    
                                
                                if type(scale) == bool:
                                    pass
                                else:
                                    fl, scale_data, info = ring_sub.scale(row, w,GLON_new_min,GLON_new_max,
                                                                        GLAT_min, GLAT_max, scale, star_dic, 
                                                                        'train', Ring_CATA, data, fits_path)
                                    
                                    if fl:
                                        append_data(scale_data, info, mwp_ring_list_train, frame_mwp_train)
                            else:
                                if type(scale) == bool:
                                    pass
                                else:
                                    fl, scale_data, info = ring_sub.scale(row, w,GLON_new_min,GLON_new_max,
                                                                        GLAT_min, GLAT_max, scale, star_dic, 
                                                                        'train', Ring_CATA, data, fits_path)
                                    
                                    if fl:
                                        append_data(scale_data, info, mwp_ring_list_train, frame_mwp_train)

    frame_mwp_train = pd.DataFrame(frame_mwp_train)
    frame_mwp_train['id']  = [i for i in range(len(frame_mwp_train))]

    print('train_count  ',  train_count)
    print('train_nan_count  ',  train_nan_count)

    # for mm in mwp_ring_list_train:
    #     print(mm.shape)

    mwp_ring_list_train = np.array(mwp_ring_list_train).astype(np.float32)
    
    savedir_name = name

    if os.path.exists(savedir_name):
        pass
    else:
        os.mkdir(savedir_name)

    # mwp_ring_list_train_ = np.array(mwp_ring_list_train)
    mwp_ring_list_train_ = mwp_ring_list_train*255
    mwp_ring_list_train_ = np.uint8(mwp_ring_list_train_)
    proceesing.data_view_rectangl(25, mwp_ring_list_train_, frame_mwp_train).save(savedir_name + '/train_ring.pdf')

    width = []
    for i in range(len(frame_mwp_train)):
        row = frame_mwp_train.iloc[i]
        for k in range(len(row['xmin'])):
            xmin = 300*row['xmin'][k]
            xmax = 300*row['xmax'][k]
            ymin = 300*row['ymin'][k]
            ymax = 300*row['ymax'][k]
            
            width.append(xmax-xmin)
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.hist(width, bins=100)
    ax.set_xlabel('width_pix')
    ax.set_ylabel('number')
    fig.savefig(savedir_name + '/width.png')


    x_cen = []
    y_cen = []
    for i in range(len(frame_mwp_train)):
        row = frame_mwp_train.iloc[i]
        for k in range(len(row['xmin'])):
            xmin = 300*row['xmin'][k]
            xmax = 300*row['xmax'][k]
            ymin = 300*row['ymin'][k]
            ymax = 300*row['ymax'][k]
            
            x_cen.append((xmax+xmin)/2)
            y_cen.append((ymax+ymin)/2)
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.scatter(x_cen, y_cen, s=0.05)
    plt.axes().set_aspect('equal') 
    ax.set_xlabel('x center')
    ax.set_ylabel('y center')

    fig.savefig(savedir_name + '/center.png')

    print('train_Ring_num : ', len(mwp_ring_list_train))
    print('train_Ring_label_num : ', len(frame_mwp_train))

    return mwp_ring_list_train, frame_mwp_train



