package probe

import (
	"go/ast"
	"go/parser"
	"go/token"
	"math/bits"
	"math/rand"
	"testing"
)

func TestAdditionEdges(t *testing.T) {
	cases := []struct{ a, b, want uint32 }{
		{0, 0, 0}, {1, 2, 3}, {0xffffffff, 1, 0}, {0xffffffff, 0xffffffff, 0xfffffffe},
		{0x7fffffff, 1, 0x80000000}, {0x80000000, 0x80000000, 0},
		{0xaaaaaaaa, 0x55555555, 0xffffffff},
	}
	for _, tc := range cases {
		if got := P2Add(tc.a, tc.b); got != tc.want {
			t.Fatalf("%08x + %08x: got %08x want %08x", tc.a, tc.b, got, tc.want)
		}
	}
}
func TestDeterministicRandomReference(t *testing.T) {
	r := rand.New(rand.NewSource(20260907))
	for i := 0; i < 10000; i++ {
		a, b := r.Uint32(), r.Uint32()
		sum := uint32(uint64(a) + uint64(b))
		mix := uint32(uint64(bits.RotateLeft32(a^b, 5)) + uint64(a) + (1 << 32) - uint64(b))
		if P2Add(a, b) != sum || P2Mix(a, b) != mix {
			t.Fatalf("case %d failed", i)
		}
	}
}
func TestPayloadScope(t *testing.T) {
	file, err := parser.ParseFile(token.NewFileSet(), "arith.go", nil, parser.ParseComments)
	if err != nil {
		t.Fatal(err)
	}
	if len(file.Imports) != 0 || len(file.Decls) != 2 {
		t.Fatal("keep payload import-free and scalar")
	}
	for _, decl := range file.Decls {
		f, ok := decl.(*ast.FuncDecl)
		if !ok || f.Recv != nil || f.Doc == nil {
			t.Fatal("unexpected payload declaration")
		}
	}
}
