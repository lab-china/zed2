import os, json, quaternion, open3d
import numpy as np
from easydict import EasyDict

def lms_regression_for_3d_pcd(pcd, out_idx=2):
  axis = [0, 1, 2]
  assert out_idx in axis
  points = np.array(pcd.points)
  colors = np.array(pcd.colors)
  # outについて線形回帰実施(入力はin0とin1)。
  axis.remove(out_idx)
  in_idx0, in_idx1 = axis[0], axis[1]
  # データ準備
  out, in0, in1 = points[:, out_idx], points[:, in_idx0], points[:, in_idx1]
  # http://reliawiki.org/index.php/Multiple_Linear_Regression_Analysis
  # "Estimating Regression Models Using Least Squares"
  # （最小二乗法で一気にパラメータを計算する手法。）
  # http://www.banbeichadexiaojiubei.com/index.php/2019/12/24/3d%E5%B9%B3%E9%9D%A2%E6%8B%9F%E5%90%88%E7%AE%97%E6%B3%95%E6%8B%9F%E5%90%88lidar%E7%82%B9%E4%BA%91/
  in0in1 = np.vstack([in0, in1]).T  # vstack + transposeにするのは回帰座標の調整上必要
  in0in1 = np.hstack([np.ones((in0in1.shape[0], 1)).astype(in0in1.dtype), in0in1]) # [1, β0, β1]
  bhat = np.linalg.inv(in0in1.T @ in0in1) @ in0in1.T @ out
  ohat = (in0in1 @ bhat).reshape(-1, 1)  
  # out_idx毎に出力順序が異なるので、それに対応させ、points2を作成
  res = {in_idx0:in0.reshape(-1, 1), in_idx1:in1.reshape(-1, 1), out_idx:ohat}  
  points2 = np.hstack([res[i] for i in [0,1,2]])
  # out_idxの値毎に色を変え, colors2を作成
  color = np.array([255 if i == out_idx else 0 for i in range(3)]).astype(colors.dtype)
  colors2 = np.zeros(colors.shape).astype(colors.dtype)
  colors2[:] = color
  plane_parameter = {'const':bhat[0], in_idx0:bhat[1], in_idx1:bhat[2], out_idx:1.}
  pcd2 = open3d.geometry.PointCloud()
  pcd2.points = open3d.utility.Vector3dVector(points2)
  pcd2.colors = open3d.utility.Vector3dVector(colors2)
  return pcd2, plane_parameter

def get_plane_parameters(p):
  f = f"{p}/pcd_extracted.ply"
  pcd = open3d.io.read_point_cloud(f)
  pcds, plane_parameters = {}, {}
  for i, ax in enumerate(['x', 'y', 'z']):
    pcds[ax], plane_parameters[ax] = lms_regression_for_3d_pcd(pcd, out_idx=i)
    open3d.io.write_point_cloud(
      f"{f.replace('.ply','')}_plane_{ax}.ply", pcds[ax])
    json.dump(plane_parameters[ax], 
      open(f"{f.replace('.ply','')}_plane_{ax}.json", 'w'), indent=2)
  return pcds, plane_parameters

def mul_quaternion(q0, q1):
  right = np.array([q1.w, q1.x, q1.y, q1.z]).reshape(-1,1)
  left = np.array([
    [q0.w, -q0.x, -q0.y, -q0.z],
    [q0.x,  q0.w, -q0.z,  q0.y],
    [q0.y,  q0.z,  q0.w, -q0.x],
    [q0.z, -q0.y,  q0.x,  q0.w]])
  return np.quaternion(*(left @ right).reshape(-1))

def get_rotation_quaternion(alpha, axis=np.array([1., 1., 1.]), is_degree=True):
  # https://showa-yojyo.github.io/notebook/python-quaternion.html#id13
  # https://en.wikipedia.org/wiki/Quaternions_and_spatial_rotation
  # https://en.wikipedia.org/wiki/File:Euler_AxisAngle.png
  assert isinstance(alpha, float)
  assert isinstance(axis, np.ndarray)
  assert axis.shape == (3,)
  # alpha should be radian
  alpha_half = np.deg2rad(alpha / 2) if is_degree else alpha / 2
  cosa = np.cos(alpha_half)
  sina = np.sin(alpha_half)
  norm = np.linalg.norm(axis)
  v = sina * (axis / norm) 
  return np.quaternion(cosa, *v)

def get_quaternion_from_vector(vec):
  return np.quaternion(0., *vec)

def get_normalized_vector(json_path=None, array=None):
  if not json_path is None:
    source = json.load(open(json_path))
    assert len([k for k in source.keys() if k in ['0','1','2']]) == 3
    vector = np.array([source[a] for a in ['0','1','2']])
    vector /= np.linalg.norm(vector)
    return vector
  elif not array is None:
    assert isinstance(array, np.ndarray)
    assert array.shape == (3,)
    vector = array / np.linalg.norm(array)
    return vector
  else:
    print('please input json_path or numpy array')
    return None

def get_rot_quaternion_from_vectors(source_vector, target_vector):
  """
    source_vectorをtarget_vectorに回転する
    quaternionの取得

    回転元ベクトルと回転先ベクトルの
    「平均ベクトル」を中心に180°回転させて
    回転のquaternionを取得する。
  """
  assert isinstance(source_vector, np.ndarray)
  assert isinstance(target_vector, np.ndarray)
  src_vec = get_normalized_vector(array=source_vector)
  tgt_vec = get_normalized_vector(array=target_vector)
  mean_vec= get_normalized_vector(array=(tgt_vec + src_vec)/2)
  q = get_rotation_quaternion(180., mean_vec)
  return q

def apply_rotation_quaternion(q, positions):
  assert isinstance(q, quaternion.quaternion)
  assert isinstance(positions, np.ndarray)
  """
  https://kamino.hatenablog.com/entry/rotation_expressions#sec3_2
  クォータニオンを使って点 p=(x,y,z) を回転させるときは、
  点pを p_q = 0 + xi + yj + zk と読み替え、以下のように計算する。
    p_q_rot = q * p_q * q.conj()
  
  * positionsはplyから読み込んだpcd.points。
  * forループだと効率が悪いので、行列で一気に計算するのもあり。
    mul_quaternion()がクォータニオンの乗算の原理。
    right変数の列数を増やせば1回の行列積で演算可能。
  """

def verify_apply_rotation(p0):
  p = f'{p0}/pcd_extracted_plane_x.json'
  src_vec = get_normalized_vector(json_path=p)
  tgt_vec = np.array([0., 1., 0.])
  q = get_rot_quaternion_from_vectors(src_vec, tgt_vec)
  p_q = np.quaternion(*([0.] + list(src_vec)))
  # if q is correctly difined, 
  # src_vec will be tgt_vec after applying rotation by q.
  q_tgt = q * get_quaternion_from_vector(src_vec) * q.conj()
  # ASSERTION:
  #   q_tgt is quaternion, and tgt.vec is its vector.
  #   if q is collectly defined, 
  #     q_tgt.vec - tgt_vec will be near zero.
  assert abs(q_tgt.vec - tgt_vec).max() < 1e-15

if __name__ == '__main__':
  root_dir = 'C:/Users/003420/Desktop/Works/NICT/predevelopment/Zed2'
  base = 'data/toYOU_20201021_'
  os.chdir(root_dir)
  for p in ["20201015155835", "20201015155844"]:
    p0 = f"{base}/{p}"
    _ = get_plane_parameters(p0)
  verify_apply_rotation(f"{base}/20201015155844")
