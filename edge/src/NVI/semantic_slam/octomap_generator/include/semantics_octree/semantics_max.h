/**
* \author Xuan Zhang
* \data Mai-July 2018
*/
#ifndef SEMANTICS_MAX_H
#define SEMANTICS_MAX_H

#include <octomap/ColorOcTree.h>
#include <set>

namespace octomap
{
  extern std::set<int> cmaps;
  /// Structure contains semantic colors and their confidences
  struct SemanticsMax
  {
    ColorOcTreeNode::Color semantic_color; ///<Semantic color
    float confidence;

    SemanticsMax():semantic_color(), confidence(0.){}

    bool operator==(const SemanticsMax& rhs) const
    {
        return semantic_color == rhs.semantic_color
                && confidence == rhs.confidence;
    }

    bool operator!=(const SemanticsMax& rhs) const
    {
        return !(*this == rhs);
    }

    ColorOcTreeNode::Color getSemanticColor() const
    {
      return semantic_color;
    }

    bool isSemanticsSet() const
    {
      if(semantic_color != ColorOcTreeNode::Color(255,255,255))
        return true;
      return false;
    }

    /// Perform max fusion
    static SemanticsMax semanticFusion(const SemanticsMax s1, const SemanticsMax s2)
    {
      SemanticsMax ret;
      // If the same color, update the confidence to the average
      if(s1.semantic_color == s2.semantic_color)
      {
        ret.semantic_color = s1.semantic_color;
        ret.confidence = std::min(s1.confidence + s2.confidence, 1e2f);
      }
      // If color is different, keep the larger one and drop a little for the disagreement
      else
      {
        if (s1.confidence > s2.confidence){
          ret = s1;
          ret.confidence = s1.confidence - s2.confidence;
        }
        else{
          ret = s2;
          ret.confidence = s2.confidence;
        }
        // ret = s1.confidence > s2.confidence ? s1 : s2;
        // ret.confidence = std::max(s1.confidence, s2.confidence) * (1-std::min(s1.confidence, s2.confidence));
      }
      return ret;
    }
  };

  std::ostream& operator<<(std::ostream& out, SemanticsMax const& s);
}
#endif //SEMANTICS_MAX_H
