import numpy as np
import cv2
import cv2 as cv
import quaternion
# import  pyquaternion as  quaternion
from transforms3d.quaternions import quat2mat, mat2quat
# from testply import convert_xyzrgb_to_ply,make_pcd
import open3d
from IPython.display import Image, display
# import pcl
#python -m pip install numpy-quaternion
#pip install pyquaternion
#conda install -c conda-forge quaternion
# camera intrinsics
cx = 325.5
cy = 253.5
fx = 518.0
fy = 519.0
depthScale = 1000.0

colorImgs, depthImgs = [], []

bp='data/'


rgb1=cv2.imread(f"./{bp}/rgb1.png")
rgb2=cv2.imread(f"./{bp}/rgb2.png")
depth1=cv2.imread(f"./{bp}/depth1.png")[:,:,0]
depth2=cv2.imread(f"./{bp}/depth2.png")[:,:,0]

#-- Step 1: Detect the keypoints using SURF Detector
# https://pystyle.info/opencv-feature-matching/
def computeKeyPointsAndDesp(src):
    minHessian = 400
    detector = cv.xfeatures2d_SURF.create(hessianThreshold=minHessian)
    keypoints = detector.detect(src)
    #-- Draw keypoints
    img_keypoints = np.empty((src.shape[0], src.shape[1], 3), dtype=np.uint8)
    cv.drawKeypoints(src, keypoints, img_keypoints)
    #-- Show detected (drawn) keypoints
    cv.imshow('SURF Keypoints', img_keypoints)
    cv.show()
def imshow(img):
    """ndarray 配列をインラインで Notebook 上に表示する。
    """
    ret, encoded = cv2.imencode(".jpg", img)
    display(Image(encoded))
def computeKeyPointsAndDesp1(img):
    # 特徴点を検出する。
    # OBR 特徴検出器を作成する。
    detector = cv2.ORB_create()
    kp = detector.detect(img)
    # 特徴点を描画する。
    dst = cv2.drawKeypoints(img, kp, None)
    kp, desc = detector.compute(img, kp)
    print(len(kp), desc.shape)
    # 特徴点を検出する。
    kp, desc = detector.detectAndCompute(img, None)
    print(len(kp), desc.shape)
    # imshow(dst)
    # cv.show()
#https://pystyle.info/opencv-feature-matching/
def computeKeyPointsAndDesp2(img1,img2):
    # OBR 特徴量検出器を作成する。
    detector = cv2.ORB_create()

    # 特徴点を検出する。
    kp1, desc1 = detector.detectAndCompute(img1, None)
    kp2, desc2 = detector.detectAndCompute(img2, None)

    # マッチング器を作成する。
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)

    # マッチングを行う。
    matches = bf.knnMatch(desc1, desc2, k=2)

    # レシオテストを行う。
    good_matches = []
    thresh = 0.7
    for first, second in matches:
        if first.distance < second.distance * thresh:
            good_matches.append(first)

    # マッチング結果を描画する。
    dst = cv2.drawMatches(img1, kp1, img2, kp2, good_matches, None)
    return kp1,kp2,good_matches
def make_pcd(points, colors):
    pcd = open3d.geometry.PointCloud()
    pcd.points = open3d.utility.Vector3dVector(points)
    pcd.colors = open3d.utility.Vector3dVector(colors)
    return pcd
def image2PointCloud(rgb, depth):
   points=[]
   colors=[]
   r,c =rgb.shape[:2]
   for i in range(r):
       for j in range(c):
           d=depth[i,j]
           if d==0:
               continue
           p=point2dTo3d([i,j,d])
           points.append(p)
           b,g,r=rgb[i,j]/255.0
           colors.append([r,g,b])
   return make_pcd(points, colors)


def merge_points_cloud(clouds):
    points=[]
    colors=[]
    for ply in clouds:
        ps=np.array(ply.points)
        cs=np.array(ply.colors)
        points.extend(ps)
        colors.extend(cs)
    return make_pcd(points,colors)
def point2dTo3d(point):
    z=point[2]/depthScale
    x=(point[0]-cx)*z/fx
    y=(point[1]-cy)*z/fy
    return [x,y,z]
def get_good_matches_pts(goodMatches,kp1,kp2):
    '''
     // 第一个帧的三维点
    vector<cv::Point3f> pts_obj;
    // 第二个帧的图像点
    vector< cv::Point2f > pts_img;

    // 相机内参
    for (size_t i=0; i<goodMatches.size(); i++)
    {
        // query 是第一个, train 是第二个
        cv::Point2f p = frame1.kp[goodMatches[i].queryIdx].pt;
        // 获取d是要小心！x是向右的，y是向下的，所以y才是行，x是列！
        ushort d = frame1.depth.ptr<ushort>( int(p.y) )[ int(p.x) ];
        if (d == 0)
            continue;
        pts_img.push_back( cv::Point2f( frame2.kp[goodMatches[i].trainIdx].pt ) );

        // 将(u,v,d)转成(x,y,z)
        cv::Point3f pt ( p.x, p.y, d );
        cv::Point3f pd = point2dTo3d( pt, camera );
        pts_obj.push_back( pd );
    }

    '''
    pts_obj=[]
    pts_img=[]
    for i, goodMatch in enumerate(goodMatches):
        p=np.array(kp1[goodMatch.queryIdx].pt,dtype=np.int)
        d=depth1[p[1],p[0]]
        if d == 0:
            continue;
        pts_img.append(kp2[goodMatch.trainIdx].pt)
        pt=[p[0],p[1],d]
        pd = point2dTo3d(pt)
        # 将(u,v,d)转成(x,y,z)
        pts_obj.append(pd)
    if len(pts_obj)==0 or len(pts_img)==0:
        return -1
    # double
    # camera_matrix_data[3][3] = {
    #     {camera.fx, 0, camera.cx},
    #     {0, camera.fy, camera.cy},
    #     {0, 0, 1}
    cameraMatrix=[
        [fx,0,cx],
        [0,fy,cy],
        [0,0,1]
        ]
    distCoeffs=[0, 0, 0, 0, 0]
    pts_img=np.array(pts_img,dtype=np.float32)
    pts_obj = np.array(pts_obj, dtype=np.float32)
    cameraMatrix = np.array(cameraMatrix, dtype=np.float64)
    distCoeffs = np.array(distCoeffs, dtype=np.float64)
    _, rVec, tVec = cv2.solvePnP(pts_obj, pts_img, cameraMatrix, distCoeffs)
    # Rt = cv2.Rodrigues(rVec)
    # R = Rt.transpose()
    #https://www.366service.com/jp/qa/ed8c0298cc30a02ee80c3d9ecef63a69
    rotM = cv2.Rodrigues(rVec)[0]
    rotM=np.array(rotM).T
    # tVec=-np.array(rotM).T * np.expand_dims(tVec,axis=0)
    cameraPosition = -np.array(rotM).T * np.array(tVec)
    rotation_mat, _ = cv2.Rodrigues(rVec)
    pose_mat = cv2.hconcat((rotM, tVec))
    #https://programtalk.com/python-examples/cv2.solvePnP/
    pose_mat=cv2.vconcat((pose_mat,np.array([[0.0,0.0,0.0,1.0]])))
    return pose_mat
kp1,kp2,goodMatches=computeKeyPointsAndDesp2(rgb1,rgb2)
pose_mat=get_good_matches_pts(goodMatches,kp1,kp2)
cloud1=image2PointCloud(rgb1,depth1)
cloud2=image2PointCloud(rgb2,depth2)
cloud2t=cloud2.transform(pose_mat)
pcd=merge_points_cloud([cloud1,cloud2t])

open3d.io.write_point_cloud('pcd_merge_org1.ply', cloud1)
open3d.io.write_point_cloud('pcd_merge_org2.ply', cloud2)
open3d.io.write_point_cloud('pcd_merge.ply', pcd)