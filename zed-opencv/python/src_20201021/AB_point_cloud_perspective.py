import os,itertools,json,open3d,struct
import numpy as np
from PIL import Image
from easydict import EasyDict
base_dir = 'C:/00_work/05_src/data'
import cv2
from move_pcds import move_pcds_by_frame,pcd_to_ply
from outlier_detect import outlier_detection
import pandas as pd
def convert_bgra2rgba(img):
  # ZED2 numpy color is BGRA.
  rgba = np.zeros(img.shape).astype(np.uint8)
  rgba[:,:,0] = img[:,:,2] # R
  rgba[:,:,1] = img[:,:,1] # G
  rgba[:,:,2] = img[:,:,0] # B
  rgba[:,:,3] = img[:,:,3] # A
  return rgba
def save_image_as_png(p, convert=True):
  color = np.load(f'{p}/image.npy')
  color = convert_bgra2rgba(color) if convert else color
  pil_img = Image.fromarray(color.astype(np.uint8))
  pil_img.save(f'{p}/image.png')


def convert_zed2pcd_to_ply(zed_pcd):
  zed_points = zed_pcd[:,:,:3]
  zed_colors = zed_pcd[:,:,3]
  points, colors = [], []
  for x, y in itertools.product(
    [a for a in range(zed_colors.shape[0])],
    [a for a in range(zed_colors.shape[1])]):
    if zed_points[x, y].sum() == 0. and zed_points[x, y].max() == 0.:
      continue
    if np.isinf(zed_points[x, y]).any() or  np.isnan(zed_points[x, y]).any():
      continue
    # color
    tmp = zed_depthfloat_to_abgr(zed_colors[x, y])
    tmp = [tmp[3], tmp[2], tmp[1]] # ABGR to RGB
    tmp = np.array(tmp).astype(np.float64) / 255. # for ply (color is double)
    colors.append(tmp)
    # point
    tmp = np.array(zed_points[x, y]).astype(np.float64)
    points.append(tmp)
  return make_pcd(points, colors)

def make_pcd(points, colors):
  pcd = open3d.geometry.PointCloud()
  pcd.points = open3d.utility.Vector3dVector(points)
  pcd.colors = open3d.utility.Vector3dVector(colors)
  return pcd
def zed_depthfloat_to_abgr(f):
  """
    ZED pcd data format:
      ----------------------------------------------------------
      https://www.stereolabs.com/docs/depth-sensing/using-depth/
      ----------------------------------------------------------
      The point cloud stores its data on 4 channels using 32-bit
      float for each channel.
      The last float is used to store color information, where
      R, G, B, and alpha channels (4 x 8-bit) are concatenated
      into a single 32-bit float.
  """
  # https://stackoverflow.com/questions/23624212/how-to-convert-a-float-into-hex/38879403
  if f == 0.:
    return [0,0,0,0]
  else:
    h = hex(struct.unpack('<I', struct.pack('<f', f))[0])
    return [eval('0x'+a+b) for a, b in zip(h[::2], h[1::2]) if a+b != '0x']

#######*************************************************
#######*************************************************
def perspective_ch(pts_src,pcd):
  pts_src[:,0]=pts_src[:,0]-min(pts_src[:,0])
  pts_src[:,1]=pts_src[:,1]-min(pts_src[:,1])
  pts_src_n=np.float32(np.array([pts_src[0],pts_src[3],pts_src[1],pts_src[2]]))
  rows,cols=pcd.shape[:2]
  pts_dst = np.float32([[0, 0], [cols, 0], [0, rows], [cols, rows]])

  M = cv2.getPerspectiveTransform(pts_src_n,pts_dst)
  # print(M)
  pcd_dst = cv2.warpPerspective(pcd, M, (cols, rows))
  return pcd_dst,M
def extract_in_4point_pcd(d):
  zed2pcd = np.load(f"{d}/pcd.npy")
  pt = json.load(open(f'{d}/frame.json'))['extract_frame_wh']
  pta=np.array(pt)
  sH,eH=min(pta[:,0]),max(pta[:,0])
  sR,eR=min(pta[:,1]),max(pta[:,1])
  pcd_frame=zed2pcd[sR:eR,sH:eH,:]
  pcd_dst,M=perspective_ch(pta,pcd_frame)

  return pcd_dst,M

base_dir = 'C:/00_work/05_src/data/frm_t'
pcds=[]
for p in os.listdir(base_dir):
  d = f'{base_dir}/{p}'
  if os.path.isdir(d):
    pcd_dst,M=extract_in_4point_pcd(d)
    pcds.append([pcd_dst,p])

    df = pd.DataFrame(M)
    filename = base_dir + '/' + p + '_matrix_perspective_0'
    df.to_csv(filename + '.csv', sep=' ', header=None, index=None)
pcda,pa=pcds[0]
pcdb,pb=pcds[1]
k=2
rc_a=np.subtract(pcda.shape[:2],k)
rc_b=np.subtract(pcdb.shape[:2],k)
frame=np.array([rc_a,rc_b])
rows,cols=max(frame[:,0]),max(frame[:,1])

rows_a,cols_a=rc_a
rows_b,cols_b=rc_b
src_a=np.float32([[0, 0], [cols_a, 0], [0, rows_a], [cols_a, rows_a]])
src_b=np.float32([[0, 0], [cols_b, 0], [0, rows_b], [cols_b, rows_b]])
pts_dst = np.float32([[0, 0], [cols, 0], [0, rows], [cols, rows]])

pyln=convert_zed2pcd_to_ply(pcda)
filename = base_dir+'/'+pa+'_extracted_frame.ply'
open3d.io.write_point_cloud(filename, pyln)

pyln=convert_zed2pcd_to_ply(pcdb)
filename = base_dir+'/'+pb+'_extracted_frame.ply'
open3d.io.write_point_cloud(filename, pyln)

##****perspective
M = cv2.getPerspectiveTransform(src_a, pts_dst)
pcd_dst_a = cv2.warpPerspective(pcda, M, (cols, rows))
pyln=convert_zed2pcd_to_ply(pcd_dst_a)
filename = base_dir+'/'+pa+'_extracted_frame_perspective.ply'
open3d.io.write_point_cloud(filename, pyln)
df = pd.DataFrame(M)
filename = base_dir+'/'+pa+'_matrix_perspective'
df.to_csv(filename + '.csv', sep=' ', header=None, index=None)

M = cv2.getPerspectiveTransform(src_b, pts_dst)
df = pd.DataFrame(M)
filename = base_dir+'/'+pb+'_matrix_perspective'
df.to_csv(filename + '.csv', sep=' ', header=None, index=None)
pcd_dst_b = cv2.warpPerspective(pcda, M, (cols, rows))
pyln=convert_zed2pcd_to_ply(pcd_dst_b)
filename = base_dir+'/'+pb+'_extracted_frame_perspective.ply'
open3d.io.write_point_cloud(filename, pyln)




#move pcd to the same position
pcds=[pcd_dst_a,pcd_dst_b]
wa,ha=pcd_dst_a.shape[:2]
wb,hb=pcd_dst_b.shape[:2]
k=10
# train_x=pcd_dst_a[:,:,:3].reshape(-1,3)
# y_pre=outlier_detection(train_x)
# frames=[[k,k,wa-k,ha-k],[k,k,wb-k,hb-k]]
# pcds_mv=move_pcds_by_frame(pcds, frames)
# for pcd_mv,id in zip(pcds_mv,[pa,pb]):
#   pyln=pcd_to_ply(pcd_mv)
#   fn=base_dir+'/'+id+'add_frame_'+'_mv.ply'
#   open3d.io.write_point_cloud(fn, pyln)

def pcd_resize(pcds,flg=0):
  pcd_size_lst=[]
  xMean_base,yMean_base,zMean_base=1,1,1
  for i,pcd in enumerate(pcds):
      xMean,yMean,zMean=np.mean(pcd[:,:,0]),np.mean(pcd[:,:,1]),np.mean(pcd[:,:,2])
      if i==0:
        xMean_base, yMean_base, zMean_base=xMean,yMean,zMean
        pcd_size_lst.append(pcd)
        continue
      rate = np.divide(np.array([xMean_base, yMean_base, zMean_base]),np.array([xMean,yMean,zMean]))
      pcd[:,:,:3]=np.multiply(pcd[:,:,:3],rate)
      pcd_size_lst.append(pcd)

  return pcd_size_lst
#resize pcd to the same size
# pcd_size_lst=pcd_resize(pcds_mv)
# for pcd_resize,id in zip(pcd_size_lst,[pa,pb]):
#   pyln=pcd_to_ply(pcd_resize)
#   fn=base_dir+'/'+id+'add_frame_'+'_resize.ply'
#   open3d.io.write_point_cloud(fn, pyln)