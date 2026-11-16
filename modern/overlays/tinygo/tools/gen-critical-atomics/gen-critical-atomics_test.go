package main

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestAtomicCompareExchangeABI(t *testing.T) {
	var source bytes.Buffer
	if err := tmpl.Execute(&source, nil); err != nil {
		t.Fatal(err)
	}
	if err := tmpl.ExecuteTemplate(&source, "atomics", 1); err != nil {
		t.Fatal(err)
	}
	code := strings.Replace(source.String(), "//go:build baremetal && !tinygo.wasm", "", 1)
	code = strings.Replace(code, "package runtime", "package atomicfixture", 1)
	code += "\nfunc lockAtomics() uintptr { return 0 }\nfunc unlockAtomics(uintptr) {}\n"
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "atomics.go"), []byte(code), 0600); err != nil {
		t.Fatal(err)
	}
	generic, err := os.ReadFile("../../src/runtime/atomics_p2_generic.go")
	if err != nil {
		t.Fatal(err)
	}
	genericCode := strings.Replace(string(generic), "//go:build p2", "", 1)
	genericCode = strings.Replace(genericCode, "package runtime", "package atomicfixture", 1)
	if err := os.WriteFile(filepath.Join(dir, "generic.go"), []byte(genericCode), 0600); err != nil {
		t.Fatal(err)
	}
	var checks strings.Builder
	checks.WriteString("package atomicfixture\nimport (\"testing\"; \"unsafe\")\n")
	for _, bits := range []int{8, 16, 32, 64} {
		fmt.Fprintf(&checks, `
func TestCAS%d(t *testing.T) {
	value := uint%d(17)
	expected := uint%d(11)
	if __atomic_compare_exchange_%d(&value, &expected, 29, 5, 5) {
		t.Fatal("mismatching CAS succeeded")
	}
	if value != 17 || expected != 17 {
		t.Fatalf("failed CAS: value=%%d expected=%%d", value, expected)
	}
	if !__atomic_compare_exchange_%d(&value, &expected, 29, 5, 5) {
		t.Fatal("matching CAS failed")
	}
	if value != 29 || expected != 17 {
		t.Fatalf("successful CAS: value=%%d expected=%%d", value, expected)
	}
	if old := __sync_val_compare_and_swap_%d(&value, 11, 43); old != 29 || value != 29 {
		t.Fatal("legacy CAS failed to return the observed value")
	}
}
`, bits, bits, bits, bits/8, bits/8, bits/8)
	}
	checks.WriteString(`
func TestGenericUnalignedAtomics(t *testing.T) {
 for size := uintptr(1); size <= 16; size++ {
  var original, result, desired, expected [20]byte
  for i := range original { original[i] = byte(i + 11); desired[i] = byte(i + 79) }
  ptr := unsafe.Pointer(&original[1])
  out := unsafe.Pointer(&result[2])
  val := unsafe.Pointer(&desired[3])
  exp := unsafe.Pointer(&expected[1])
  p2AtomicLoad(size, ptr, out, 5)
  for i := uintptr(0); i < size; i++ { if result[i+2] != original[i+1] { t.Fatal("generic load") } }
  if p2AtomicCompareExchange(size, ptr, exp, val, 5, 5) { t.Fatal("generic failed CAS succeeded") }
  for i := uintptr(0); i < size; i++ { if expected[i+1] != original[i+1] { t.Fatal("generic failed CAS expected update") } }
  if !p2AtomicCompareExchange(size, ptr, exp, val, 5, 5) { t.Fatal("generic matching CAS failed") }
  for i := uintptr(0); i < size; i++ { if original[i+1] != desired[i+3] { t.Fatal("generic CAS desired value") } }
  p2AtomicExchange(size, ptr, exp, out, 5)
  for i := uintptr(0); i < size; i++ {
   if result[i+2] != desired[i+3] || original[i+1] != expected[i+1] { t.Fatal("generic exchange") }
  }
  p2AtomicStore(size, ptr, val, 5)
  for i := uintptr(0); i < size; i++ { if original[i+1] != desired[i+3] { t.Fatal("generic store") } }
 }
}
`)
	if err := os.WriteFile(filepath.Join(dir, "atomics_test.go"), []byte(checks.String()), 0600); err != nil {
		t.Fatal(err)
	}
	cmd := exec.Command("go", "test", "-v")
	cmd.Dir = dir
	cmd.Env = append(os.Environ(), "GO111MODULE=off", "GOWORK=off")
	if output, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("generated atomic ABI regression: %v\n%s", err, output)
	} else {
		t.Logf("%s", output)
	}
}
