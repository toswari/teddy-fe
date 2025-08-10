import numpy as np
import pytest
from clarifai_pff.auto_homography import associate_line_to_yard, conflict_dfs

@pytest.fixture
def sample_proto_lines():
    # 3 lines in xym format (x, y, m)
    return np.array([
        [10, 0, 1e7],
        [15, 0, 1e7],
        [20, 0, 1e7],
        [25, 0, 1e7],
        [30, 0, 1e7],
    ])

@pytest.fixture
def sample_yard_boxes():
    # 3 boxes: (x, y, w, h)
    return np.array([
        [10, 0, 3, 2],   # covers line 1
        [20, 0, 3, 2],  # covers line 3
        [30, 0, 3, 2],  # covers line 4
    ])

@pytest.fixture
def sample_yard_labels():
    return np.array([10, 20, 30])

@pytest.fixture
def sample_yard_labels_straddle():
    return np.array([40, 50, 40])

@pytest.fixture
def sample_yard_labels_right():
    return np.array([40, 30, 20])

@pytest.fixture
def sample_proto_lines_single():
    # 1 line in xym format (x, y, m)
    return np.array([
        [10, 0, 1e7],
    ])

@pytest.fixture
def sample_yard_boxes_single():
    # 1 box: (x, y, w, h)
    return np.array([
        [10, 0, 3, 2],
        [15, 0, 3, 2],
    ])

@pytest.fixture
def sample_yard_labels_single():
    return np.array([10])

def test_associate_line_to_yard_basic(sample_proto_lines, sample_yard_boxes, sample_yard_labels):
    result, result_imap = associate_line_to_yard(sample_proto_lines, sample_yard_boxes, sample_yard_labels, 100)
    # Should return a mapping for each proto_line to its yard label
    assert result is not None
    assert result_imap is not None
    # The mapping should have as many rows as proto_lines
    assert result.shape[0] == sample_proto_lines.shape[0]

    # labels should include yard labels and interpolated values
    assert {10,15,20,25,30} == set(map(int, result[:,1]))

def test_associate_line_to_yard_straddle(sample_proto_lines, sample_yard_boxes, sample_yard_labels_straddle):
    result, result_imap = associate_line_to_yard(sample_proto_lines, sample_yard_boxes, sample_yard_labels_straddle, 100)
    # Should return a mapping for each proto_line to its yard label
    assert result is not None
    assert result_imap is not None
    # The mapping should have as many rows as proto_lines
    assert result.shape[0] == sample_proto_lines.shape[0]

    # labels should include yard labels and interpolated values
    assert {40,45,50,55,60} == set(map(int, result[:,1]))

def test_associate_line_to_yard_right(sample_proto_lines, sample_yard_boxes, sample_yard_labels_right):
    result, result_imap = associate_line_to_yard(sample_proto_lines, sample_yard_boxes, sample_yard_labels_right, 100)
    # Should return a mapping for each proto_line to its yard label
    assert result is not None
    assert result_imap is not None
    # The mapping should have as many rows as proto_lines
    assert result.shape[0] == sample_proto_lines.shape[0]

    # labels should include yard labels and interpolated values
    assert {60,65,70,75,80} == set(map(int, result[:,1]))

def test_associate_line_to_yard_single(sample_proto_lines_single, sample_yard_boxes_single, sample_yard_labels_single):
    result, result_imap = associate_line_to_yard(sample_proto_lines_single, sample_yard_boxes_single, sample_yard_labels_single, 100)
    # Should return a mapping for each proto_line to its yard label
    assert result is not None
    assert result_imap is not None
    # The mapping should have as many rows as proto_lines
    assert result.shape[0] == sample_proto_lines_single.shape[0]

    # labels should include yard labels and interpolated values
    assert {10} == set(map(int, result[:,1]))

def test_associate_line_to_yard_no_intersection(sample_proto_lines, sample_yard_labels):
    # Move boxes far away so no intersection
    yard_boxes = np.array([
        [100, 100, 2, 5],
        [200, 100, 2, 5],
        [300, 100, 2, 5],
    ])
    result, result_imap = associate_line_to_yard(sample_proto_lines, yard_boxes, sample_yard_labels, 100)
    # Should handle gracefully (likely empty or with -1 labels)
    assert result is not None
    assert (result[:,1] == -1).all() or result.shape[0] == 0

def test_associate_line_to_yard_duplicate_labels(sample_proto_lines, sample_yard_boxes):
    # Duplicate labels
    yard_labels = np.array([10, 10, 30])
    result, result_imap = associate_line_to_yard(sample_proto_lines, sample_yard_boxes, yard_labels, 100)
    # Should still map, but may have duplicate label assignments
    assert result is not None
    # 2 + 1 for labels + interpolated value
    assert (result[:,1] == 10).sum() == 3
    assert (result[:,1] == 30).sum() == 1

def test_conflict_dfs_no_intersection():
    proto_lines = np.array([
        [20, 0, 1e7],
        [25, 0, 1e7],
        [30, 0, 1e7],
    ])
    boxes = np.array([
        [100, 100, 2, 5],
        [200, 100, 2, 5],
        [300, 100, 2, 5],
    ])
    labels = np.array([10, 20, 30])

    visited = set()
    out = []
    conflict_dfs(proto_lines, boxes, labels, 100, path=(), visited=visited, out=out)

    assert visited == {()}
    assert len(out) == 0

def test_conflict_dfs_duplicate_boxes_big_gap():
    """
    Test conflict resolution when class partitioned NMS gives 2 overlapping boxes with different labels. 
    Also happens to give a gap that is too large.
    """
    proto_lines = np.array([
        [20, 0, 1e7],
        [25, 0, 1e7],
        [30, 0, 1e7],
    ])
    boxes = np.array([
        [20, 0, 3, 2],
        [30, 0, 3, 2],
        [30, 0, 3, 2],
    ])
    labels = np.array([20, 30, 40])

    visited = set()
    out = []
    conflict_dfs(proto_lines, boxes, labels, 100, path=(), visited=visited, out=out)

    assert len(out) == 1
    out = [tuple(y.tolist() for y in x) for x in out]
    assert out == [
        (
            [[0., 20.], [1., 25.], [2., 30.]], 
            [[0,0],[2,1]],
            boxes[[0,2]].tolist()
        ),
    ]

def test_conflict_dfs_small_gap():
    """
    Test conflict resolution when boxes are classified as too far apart
    """
    proto_lines = np.array([
        [20, 0, 1e7],
        [25, 0, 1e7],
        [30, 0, 1e7],
    ])
    boxes = np.array([
        [20, 0, 3, 2],
        [40, 0, 3, 2],
    ])
    labels = np.array([20, 40])

    visited = set()
    out = []
    conflict_dfs(proto_lines, boxes, labels, 100, path=(), visited=visited, out=out)

    assert len(out) == 0

def test_conflict_dfs_duplicate_lines():
    """
    Test conflict resolution when two lines have the same label
    """
    proto_lines = np.array([
        [20, 0, 1e7],
        [25, 0, 1e7],
        [30, 0, 1e7],
        [35, 0, 1e7],
        [40, 0, 1e7],
    ])
    boxes = np.array([
        [20, 0, 3, 2],
        [30, 0, 3, 2],
        [40, 0, 3, 2],
    ])
    labels = np.array([20, 30, 30])

    visited = set()
    out = []
    conflict_dfs(proto_lines, boxes, labels, 100, path=(), visited=visited, out=out)

    assert len(out) == 1
    out = [tuple(y.tolist() for y in x) for x in out]
    assert out == [
        (
            [[0., 20.], [1., 25.], [2., 30.]], 
            [[0,0],[2,1]],
            boxes[[0,1]].tolist()
        ),
    ]

def test_conflict_dfs_box_labels():
    proto_lines = np.array([
        [20, 0, 1e7],
        [25, 0, 1e7],
        [30, 0, 1e7],
        [35, 0, 1e7],
        [40, 0, 1e7],
    ])
    boxes = np.array([
        [20, 0, 3, 2],
        [20, 10, 3, 2],
        [30, 0, 3, 2],
        [40, 0, 3, 2],
    ])
    labels = np.array([20, 30, 30, 40])

    visited = set()
    out = []
    conflict_dfs(proto_lines, boxes, labels, 100, path=(), visited=visited, out=out)
    assert len(out) == 2
    out = [tuple(y.tolist() for y in x) for x in out]
    assert out == [
        (
            [[2, 30], [3, 35], [4, 40]], 
            [[2,0],[4,1]],
            boxes[[2,3]].tolist()
        ),
        (
            [[0, 20], [1, 25], [2, 30], [3, 35], [4, 40]], 
            [[0,0],[2,1],[4,2]], # [2,1] due to dropping boxes[1]
            boxes[[0,2,3]].tolist()
        ),
    ]

def test_conflict_dfs_xxx():
    proto_lines = np.array([
        [20, 0, 1e7],
        [25, 0, 1e7],
        [30, 0, 1e7],
    ])
    boxes = np.array([
        [20, 0, 3, 2],
        [20, 5, 3, 2],
        [30, 0, 3, 2],
    ])
    labels = np.array([20, 10, 30])

    visited = set()
    out = []
    conflict_dfs(proto_lines, boxes, labels, 100, path=(), visited=visited, out=out)
    assert len(out) == 1
    out = [tuple(y.tolist() for y in x) for x in out]
    assert out == [
        (
            [[0., 20.], [1., 25.], [2., 30.]], 
            [[0,0],[2,1]],
            boxes[[0,2]].tolist()
        ),
    ]

def test_associate_line_to_yard_box_conflict():
    proto_lines = np.array([
        [20, 0, 1e7],
        [25, 0, 1e7],
        [30, 0, 1e7],
    ])
    boxes = np.array([
        [20, 0, 3, 2],
        [20, 5, 3, 2],
        [30, 0, 3, 2],
    ])
    labels = np.array([20, 10, 30])

    result, result_imap = associate_line_to_yard(proto_lines, boxes, labels, 100)
    assert result is not None
    assert result_imap is not None
    assert result.tolist() == [
        [0.0, 10.0],
        [0.0, 20.0],
        [1.0, 25.0],
        [2.0, 30.0],
    ]