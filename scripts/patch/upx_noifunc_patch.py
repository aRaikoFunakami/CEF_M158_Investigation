#!/usr/bin/env python3
"""upx_noifunc_patch.py <src> : PartitionAlloc の tagging.cc から IFUNC をなくす(冪等、M22)。
UPX で圧縮した共有ライブラリは、動的リンカが IRELATIVE 再配置で IFUNC の選択関数を呼ぶ時点では、まだコードが展開されていない。
そのため libcef.so の読み込みで SIGSEGV になる(logs/479、480)。IFUNC の 5 関数を、初回呼び出し時に同じ選択関数を
getauxval(AT_HWCAP / AT_HWCAP2) で呼んで結果を覚える普通の関数に置き換える。MTE の有無で実装を選ぶ動作は変わらない。"""
import sys
p = f'{sys.argv[1]}/base/allocator/partition_allocator/src/partition_alloc/tagging.cc'
s = open(p).read(); t = s
helper = '''#include <sys/ifunc.h>
#include <sys/auxv.h>
// FP: UPX で圧縮した共有ライブラリでも動くように IFUNC を使わない(初回呼び出し時に選択関数を呼ぶ)。
namespace {
__ifunc_arg_t* FpIfuncArg() {
  static __ifunc_arg_t a = {sizeof(__ifunc_arg_t), getauxval(AT_HWCAP), getauxval(AT_HWCAP2)};
  return &a;
}
}  // namespace
#define FP_IFUNC(R) ([] { static auto* f = R(getauxval(AT_HWCAP) | _IFUNC_ARG_HWCAP, FpIfuncArg()); return f; }())
'''
pairs = [
    ('#include <sys/ifunc.h>\n', helper),
    ('    __attribute__((ifunc("ResolveChangeMemoryTaggingModeForCurrentThread")));\n',
     '{\n  FP_IFUNC(ResolveChangeMemoryTaggingModeForCurrentThread)(m);\n}\n'),
    ('void* TagMemoryRangeIncrementInternal(void* ptr, size_t size)\n    __attribute__((ifunc("ResolveTagMemoryRangeIncrement")));\n',
     'void* TagMemoryRangeIncrementInternal(void* ptr, size_t size) {\n  return FP_IFUNC(ResolveTagMemoryRangeIncrement)(ptr, size);\n}\n'),
    ('void* TagMemoryRangeRandomlyInternal(void* ptr, size_t size, uint64_t mask)\n    __attribute__((ifunc("ResolveTagMemoryRandomly")));\n',
     'void* TagMemoryRangeRandomlyInternal(void* ptr, size_t size, uint64_t mask) {\n  return FP_IFUNC(ResolveTagMemoryRandomly)(ptr, size, mask);\n}\n'),
    ('void* RemaskPointerInternal(void* ptr)\n    __attribute__((ifunc("ResolveRemaskPointer")));\n',
     'void* RemaskPointerInternal(void* ptr) {\n  return FP_IFUNC(ResolveRemaskPointer)(ptr);\n}\n'),
    ('    __attribute__((ifunc("ResolveGetMemoryTaggingModeForCurrentThread")));\n',
     '{\n  return FP_IFUNC(ResolveGetMemoryTaggingModeForCurrentThread)();\n}\n'),
]
for old, new in pairs:
    if new in t: continue
    assert t.count(old) == 1, old
    t = t.replace(old, new)
if t != s: open(p, 'w').write(t); print('patched', p)
else: print('unchanged', p)

# 2 つ目: page_allocator_internals_posix.cc の GetAccessFlags(MTE / BTI の有無でページ保護フラグを選ぶ、logs/481 で残った IFUNC)
p = f'{sys.argv[1]}/base/allocator/partition_allocator/src/partition_alloc/page_allocator_internals_posix.cc'
s = open(p).read(); t = s
old = '    __attribute__((ifunc("ResolveGetAccessFlags")));\n'
new = ('{\n  // FP: UPX で圧縮した共有ライブラリでも動くように IFUNC を使わない(初回呼び出し時に選択関数を呼ぶ)。\n'
       '  static __ifunc_arg_t* const fp_hw = [] {\n'
       '    static __ifunc_arg_t a = {sizeof(__ifunc_arg_t), getauxval(AT_HWCAP), getauxval(AT_HWCAP2)};\n'
       '    return &a;\n  }();\n'
       '  static auto* const f = ResolveGetAccessFlags(getauxval(AT_HWCAP) | _IFUNC_ARG_HWCAP, fp_hw);\n'
       '  return f(accessibility);\n}\n')
if new not in t:
    assert t.count(old) == 1, old
    t = t.replace(old, new)
    if '#include <sys/auxv.h>' not in t:
        t = t.replace('#include <sys/mman.h>\n', '#include <sys/auxv.h>\n#include <sys/mman.h>\n', 1)
if t != s: open(p, 'w').write(t); print('patched', p)
else: print('unchanged', p)
