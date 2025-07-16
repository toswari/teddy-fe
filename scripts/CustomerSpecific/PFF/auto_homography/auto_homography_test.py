import numpy as np
import pytest
from auto_homography import associate_line_to_yard, conflict_dfs

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
    result, result_imap = associate_line_to_yard(sample_proto_lines, sample_yard_boxes, sample_yard_labels)
    # Should return a mapping for each proto_line to its yard label
    assert result is not None
    assert result_imap is not None
    # The mapping should have as many rows as proto_lines
    assert result.shape[0] == sample_proto_lines.shape[0]

    # labels should include yard labels and interpolated values
    assert {10,15,20,25,30} == set(map(int, result[:,1]))

def test_associate_line_to_yard_straddle(sample_proto_lines, sample_yard_boxes, sample_yard_labels_straddle):
    result, result_imap = associate_line_to_yard(sample_proto_lines, sample_yard_boxes, sample_yard_labels_straddle)
    # Should return a mapping for each proto_line to its yard label
    assert result is not None
    assert result_imap is not None
    # The mapping should have as many rows as proto_lines
    assert result.shape[0] == sample_proto_lines.shape[0]

    # labels should include yard labels and interpolated values
    assert {40,45,50,55,60} == set(map(int, result[:,1]))

def test_associate_line_to_yard_right(sample_proto_lines, sample_yard_boxes, sample_yard_labels_right):
    result, result_imap = associate_line_to_yard(sample_proto_lines, sample_yard_boxes, sample_yard_labels_right)
    # Should return a mapping for each proto_line to its yard label
    assert result is not None
    assert result_imap is not None
    # The mapping should have as many rows as proto_lines
    assert result.shape[0] == sample_proto_lines.shape[0]

    # labels should include yard labels and interpolated values
    assert {60,65,70,75,80} == set(map(int, result[:,1]))

def test_associate_line_to_yard_single(sample_proto_lines_single, sample_yard_boxes_single, sample_yard_labels_single):
    result, result_imap = associate_line_to_yard(sample_proto_lines_single, sample_yard_boxes_single, sample_yard_labels_single)
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
    result, result_imap = associate_line_to_yard(sample_proto_lines, yard_boxes, sample_yard_labels)
    # Should handle gracefully (likely empty or with -1 labels)
    assert result is not None
    assert (result[:,1] == -1).all() or result.shape[0] == 0

def test_associate_line_to_yard_duplicate_labels(sample_proto_lines, sample_yard_boxes):
    # Duplicate labels
    yard_labels = np.array([10, 10, 30])
    result, result_imap = associate_line_to_yard(sample_proto_lines, sample_yard_boxes, yard_labels)
    # Should still map, but may have duplicate label assignments
    assert result is not None
    # 2 + 1 for labels + interpolated value
    assert (result[:,1] == 10).sum() == 3
    assert (result[:,1] == 30).sum() == 1

def test_conflict_dfs():
    proto_lines = np.array([
        [20, 0, 1e7],
        [25, 0, 1e7],
        [30, 0, 1e7],
    ])
    boxes = np.array([
        [20, 0, 3, 2],
        [20, 30, 3, 2],
        [30, 0, 3, 2],
        [30, 30, 3, 2],
    ])
    labels = np.array([20, 30, 30, 40])

    visited = set()
    out = []
    conflict_dfs(proto_lines, boxes, labels, path=(), visited=visited, out=out)

    expected_paths = {
        (),
        (0,2),
        (0,3),
        (0,3,0),
        (0,3,1),
        (1,2),
        (1,3),
    }
    assert visited == expected_paths
    assert len(out) == 2
    out = [tuple(y.tolist() for y in x)for x in out]
    assert out == [
        (
            [[0, 30], [1,35], [2,40]], 
            [[0,0],[2,1]],
            boxes[[1,3]].tolist()
        ),
        (
            [[0, 20], [1,25], [2,30]], 
            [[0,0],[2,1]],
            boxes[[0,2]].tolist()
        ),
    ]

def test_conflict_dfs2():
    proto_lines = np.array([
        [20, 0, 1e7],
        [25, 0, 1e7],
        [30, 0, 1e7],
        [35, 0, 1e7],
        [40, 0, 1e7],
    ])
    boxes = np.array([
        [20, 0, 3, 2],
        [20, 30, 3, 2],
        [30, 0, 3, 2],
        [30, 30, 3, 2],
        [40, 0, 3, 2],
        [40, 30, 3, 2],
    ])
    labels = np.array([20, 30, 30, 40, 50, 50])

    visited = set()
    out = []
    conflict_dfs(proto_lines, boxes, labels, path=(), visited=visited, out=out)

    expected_paths = {
        (),
        (0,2),
        (0,3),
        (0,3,0),
        (0,3,1),
        (1,2),
        (1,3),
    }
    assert visited == expected_paths
    assert len(out) == 1
    out = [tuple(y.tolist() for y in x) for x in out]
    assert out == [
        (
            [[0., 30.], [1., 35.], [2., 40.], [3., 45.], [4., 50.]], 
            [[0, 0], [2, 1], [4, 2], [4, 3]],
            boxes[[1, 3, 4, 5]].tolist()
        ),
    ]