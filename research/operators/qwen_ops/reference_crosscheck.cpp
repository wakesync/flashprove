// Independent runner exports the exact C++ fixtures consumed by the proof batches.
#define main qwen_proof_test_main
#include "proof.cpp"
#undef main
static void vector_json(const std::vector<i64>& x) {
  std::cout<<'[';
  for(size_t j=0;j<x.size();j++){if(j)std::cout<<',';std::cout<<x[j];}
  std::cout<<']';
}
int main() {
  for(const std::string op:{"nonlinear","conv","l2","rms","rotary"}) for(int f:{12,14,16}) for(int seed=1;seed<=10;seed++) {
    const auto z=fixture(op,f,seed);
    std::cout<<"{\"op\":\""<<op<<"\",\"F\":"<<f<<",\"seed\":"<<seed<<",\"position\":"<<z.position<<",\"x\":";
    vector_json(z.x);std::cout<<",\"y\":";vector_json(z.y);std::cout<<"}"<<std::endl;
  }
}
