#include<semantics_octree/semantics_max.h>
namespace octomap
{
  std::set<int> cmaps={8405120,
  15213556,
  4605510,
  10249830,
  10066366,
  10066329,
  2009850,
  56540,
  2330219,
  10025880,
  11829830,
  3937500,
  255,
  9306112,
  4587520,
  6568960,
  6574080,
  15073280,
  2100087,
  16419980,
  0,
  16777215};
  std::ostream& operator<<(std::ostream& out, SemanticsMax const& s)
  {
    return out << '(' << s.semantic_color << ", " << s.confidence << ')';
  }
}
