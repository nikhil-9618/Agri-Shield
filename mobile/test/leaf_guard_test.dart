import 'package:flutter_test/flutter_test.dart';

import 'package:agrishield/core/leaf_guard.dart';

void main() {
  test('a human portrait is rejected before disease inference', () {
    final result = LeafGuard.evaluate({
      'Person': 0.91,
      'Smile': 0.72,
      'Plant': 0.31,
    });

    expect(result.isLeaf, isFalse);
    expect(result.rejection, LeafRejection.person);
  });

  test('a close-up leaf with plant labels is accepted', () {
    final result = LeafGuard.evaluate({
      'Plant': 0.74,
      'Flora': 0.58,
      'Twig': 0.33,
    });

    expect(result.isLeaf, isTrue);
    expect(result.rejection, isNull);
    expect(result.plantScore, closeTo(0.74, 0.001));
  });

  test('a non-plant object without a person label is rejected', () {
    final result = LeafGuard.evaluate({
      'Car': 0.86,
      'Vehicle': 0.71,
      'Road': 0.44,
    });

    expect(result.isLeaf, isFalse);
    expect(result.rejection, LeafRejection.noLeaf);
  });

  test('a scene label alone is not enough to count as a leaf', () {
    final result = LeafGuard.evaluate({
      'Field': 0.81,
      'Garden': 0.66,
    });

    expect(result.isLeaf, isFalse);
    expect(result.rejection, LeafRejection.noLeaf);
  });
}
