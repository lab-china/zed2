#https://stackoverflow.com/questions/56183201/detect-and-visualize-differences-between-two-images-with-opencv-python
from skimage.measure import compare_ssim
import cv2
import numpy as np


from object_detection_draw_v5 import load_image_from_npy
# load images
path='C:/00_work2/05_src/data/fromito/data/'
leftImage=f'{path}/image_average_cam0.png'
rightImage=f'{path}/image.npy'
before = cv2.imread(leftImage)
after,_ =load_image_from_npy(rightImage)
after = cv2.cvtColor(after, cv2.COLOR_BGR2RGB)
cv2.imwrite(f'{path}/image2.png', after)

#https://stackoverflow.com/questions/56183201/detect-and-visualize-differences-between-two-images-with-opencv-python
def compute_difference_ssim(before,after,color=[0, 0, 255]):
    # Convert images to grayscale
    before = cv2.GaussianBlur(before, (3, 3), 0)
    after = cv2.GaussianBlur(after, (3, 3), 0)
    before_gray = cv2.cvtColor(before, cv2.COLOR_BGR2GRAY)
    after_gray = cv2.cvtColor(after, cv2.COLOR_BGR2GRAY)

    # Compute SSIM between two images
    (score, diff) = compare_ssim(before_gray, after_gray, full=True)
    print("Image similarity", score)

    # The diff image contains the actual image differences between the two images
    # and is represented as a floating point data type in the range [0,1]
    # so we must convert the array to 8-bit unsigned integers in the range
    # [0,255] before we can use it with OpenCV
    diff = (diff * 255).astype("uint8")

    # Threshold the difference image, followed by finding contours to
    # obtain the regions of the two input images that differ
    thresh = cv2.threshold(diff, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    contours = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = contours[0] if len(contours) == 2 else contours[1]

    mask = np.zeros(before.shape, dtype='uint8')
    filled_after = after.copy()

    for c in contours:
        area = cv2.contourArea(c)
        if area > 40:
            x,y,w,h = cv2.boundingRect(c)
            cv2.rectangle(before, (x, y), (x + w, y + h), (36,255,12), 2)
            cv2.rectangle(after, (x, y), (x + w, y + h), (36,255,12), 2)
            cv2.drawContours(mask, [c], 0, color, -1)
            cv2.drawContours(filled_after, [c], 0, color, -1)
    return before,after,diff,mask,filled_after
before,after,diff,mask,filled_after=compute_difference_ssim(before,after,color=[0, 0, 255])
cv2.imwrite(f'{path}/compare_ssim_before.png', before)
cv2.imwrite(f'{path}/compare_ssim_after.png', after)
cv2.imwrite(f'{path}/compare_ssim_diff.png', diff)
cv2.imwrite(f'{path}/compare_ssim_mask.png', mask)
cv2.imwrite(f'{path}/compare_ssim_filled_after.png', filled_after)
