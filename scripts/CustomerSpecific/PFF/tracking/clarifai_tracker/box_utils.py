#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Definition of bounding boxes to use throughout training, storage, API, etc. """

import numpy as np
from PIL import Image as PILImage
from PIL import ImageDraw

def bbox_overlaps(boxes_A, boxes_B, distance_penalty=0, include_edge_pixels=True):
  '''
  Computes overlaps between boxes_A [n_A x 4] and boxes_B [n_B x 4],
  returns the [n_A x n_B] matrix of IOU overlaps.
  '''
  # broadcast shapes so that A runs on axis 0, B on axis 1, and unpack bbox coords
  (x0_A, y0_A, x1_A, y1_A) = boxes_A.T[:, :, np.newaxis]
  (x0_B, y0_B, x1_B, y1_B) = boxes_B.T[:, np.newaxis, :]

  # For pixel coords we include +1 to be consistent with edge pixels
  # but this is not required for relative coordinates
  if include_edge_pixels:
    x_I = np.maximum(0.0, np.minimum(x1_A, x1_B) - np.maximum(x0_A, x0_B) + 1)
    y_I = np.maximum(0.0, np.minimum(y1_A, y1_B) - np.maximum(y0_A, y0_B) + 1)
    a_A = (x1_A - x0_A + 1) * (y1_A - y0_A + 1)
    a_B = (x1_B - x0_B + 1) * (y1_B - y0_B + 1)
  else:
    x_I = np.maximum(0.0, np.minimum(x1_A, x1_B) - np.maximum(x0_A, x0_B))
    y_I = np.maximum(0.0, np.minimum(y1_A, y1_B) - np.maximum(y0_A, y0_B))
    a_A = (x1_A - x0_A) * (y1_A - y0_A)
    a_B = (x1_B - x0_B) * (y1_B - y0_B)

  # get intersections and union area
  a_I = x_I * y_I
  a_U = a_A + a_B - a_I

  iou = a_I / a_U

  if distance_penalty != 0:
    # add term to account for distance between centers for alignment.
    # especially in cases where a small box fits fully inside a larger box,
    # many locations have the same iou overlap
    # not applied to boxes that have no overlap (iou for these is kept at 0)
    # cx,cy: center coords of boxes (times 2)
    cx_A = (x1_A + x0_A)
    cy_A = (y1_A + y0_A)
    cx_B = (x1_B + x0_B)
    cy_B = (y1_B + y0_B)
    # mdx,mdy: max widths and heights
    mdx = np.maximum(x1_A - x0_A, x1_B - x0_B)
    mdy = np.maximum(y1_A - y0_A, y1_B - y0_B)
    # center_dist: l1 distance between centers relative to box size
    center_dist = np.minimum(1.0, np.abs(cx_A - cx_B) / mdx) \
                + np.minimum(1.0, np.abs(cy_A - cy_B) / mdy)
    # add term to iou overlaps, for boxes with any overlap
    any_overlap = (a_I > 0).astype(center_dist.dtype)
    iou += (distance_penalty * any_overlap * (2.0 - center_dist))

  return iou
