// Exact CPU host entry point used by cp_commit and cp_prove, no CUDA execution.
#include "cp_configured.h"
#include <chrono>
#include <fstream>
#include <iostream>
#include <iterator>
#include <iomanip>
static std::string read(const std::string &path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) std::exit(2);
  return {std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>()};
}
int main(int argc, char **argv) {
  if (argc != 2) return 2;
  const std::string dir = argv[1], policy = read(dir + "/policy.txt"), layout = read(dir + "/layout.txt"), kl = read(dir + "/KL.bin");
  if (kl.size() % 4) return 2;
  std::vector<uint32_t> words;
  for (size_t i = 0; i < kl.size(); i += 4) {
    uint32_t w = 0;
    for (size_t j = 0; j < 4; ++j) w |= uint32_t(uint8_t(kl[i+j])) << (8*j);
    words.push_back(w);
  }
  const auto start = std::chrono::steady_clock::now();
  return cp_with_configured(policy, layout, words, 128, true, [&](const blk::Configured &c) {
    std::cout << std::setprecision(9) << "host_configuration " << std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count() << "\n";
    std::cout << "table_rows " << c.sized().once.S.fold.index.rows() << "\n";
    std::cout << "table_columns " << c.sized().once.S.fold.index.code.n() << "\n";
    std::cout << "configuration ";
    for (auto b : blk::digest_bytes(c.configuration())) std::cout << std::hex << std::setw(2) << std::setfill('0') << unsigned(b);
    std::cout << "\n";
    return 0;
  });
}
