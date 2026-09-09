//go:build p2probe
// +build p2probe

package compiler

// Narrow integration hook for TinyGo v0.23.0, NOT a new general-purpose target.
// It invokes TinyGo's existing SSA-to-LLVM compiler and the real P2 target
// machine. It does NOT synthesize the arithmetic IR, retarget ARM IR, or invent
// runtime stubs. Runtime-dependent SSA is explicitly rejected before lowering.
//
// Add this file to compiler/ in the pinned TinyGo checkout. Existing upstream
// files are unmodified. Public CompilePackage unconditionally expects a runtime
// package and runtime.alloc; this leaf-only experiment intentionally calls the
// same internal function builder directly, without package initialization.

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"go/ast"
	"go/parser"
	"go/token"
	"go/types"
	"io/ioutil"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	"golang.org/x/tools/go/ssa"
	"tinygo.org/x/go-llvm"
)

func TestP2ScalarProof(t *testing.T) {
	source := os.Getenv("P2_PROBE_SOURCE")
	out := os.Getenv("P2_PROBE_OUT")
	if source == "" || out == "" {
		t.Skip("Set P2_PROBE_SOURCE and P2_PROBE_OUT to run the scalar experiment")
	}
	if !strings.HasPrefix(llvm.Version, "14.") {
		t.Fatalf("pinned proof requires LLVM 14 family; got %s", llvm.Version)
	}
	cfg := &Config{
		Triple: "p2", CodeModel: "default", RelocationModel: "static",
		Scheduler: "none", SizeLevel: 2, Debug: false,
		NeedsStackObjects: false, AutomaticStackSize: false,
	}
	machine, err := NewTargetMachine(cfg)
	if err != nil {
		t.Fatal(err)
	}
	defer machine.Dispose()
	td := machine.CreateTargetData()
	if td.PointerSize() != 4 {
		t.Fatalf("unexpected P2 pointer size: %d", td.PointerSize())
	}
	layout := td.String()
	td.Dispose()

	contents, err := ioutil.ReadFile(source)
	if err != nil {
		t.Fatal(err)
	}
	fset := token.NewFileSet()
	file, err := parser.ParseFile(fset, source, contents, parser.ParseComments)
	if err != nil {
		t.Fatal(err)
	}
	if len(file.Imports) != 0 {
		t.Fatal("proof forbids imports")
	}
	expected := map[string]string{"P2Add": "p2_add", "P2Mix": "p2_mix"}
	stage := os.Getenv("P2_PROBE_STAGE")
	selected := []string{"P2Add"}
	exports := []string{"p2_add"}
	switch stage {
	case "add":
	case "full":
		selected = append(selected, "P2Mix")
		exports = append(exports, "p2_mix")
	default:
		t.Fatal("P2_PROBE_STAGE must be add or full")
	}
	if len(file.Decls) != len(expected) {
		t.Fatal("proof permits exactly two function declarations")
	}
	seen := map[string]bool{}
	for _, decl := range file.Decls {
		fn, ok := decl.(*ast.FuncDecl)
		if !ok || fn.Recv != nil || fn.Body == nil {
			t.Fatal("only ordinary function definitions allowed")
		}
		if _, ok := expected[fn.Name.Name]; !ok {
			t.Fatalf("unexpected function %s", fn.Name.Name)
		}
		if seen[fn.Name.Name] {
			t.Fatal("duplicate function")
		}
		seen[fn.Name.Name] = true
	}
	info := &types.Info{
		Types: map[ast.Expr]types.TypeAndValue{}, Defs: map[*ast.Ident]types.Object{},
		Uses: map[*ast.Ident]types.Object{}, Implicits: map[ast.Node]types.Object{},
		Scopes: map[ast.Node]*types.Scope{}, Selections: map[*ast.SelectorExpr]*types.Selection{},
	}
	tc := types.Config{Sizes: Sizes(machine)}
	pkg, err := tc.Check("p2proof", fset, []*ast.File{file}, info)
	if err != nil {
		t.Fatal(err)
	}
	program := ssa.NewProgram(fset, ssa.SanityCheckFunctions|ssa.GlobalDebug)
	sp := program.CreatePackage(pkg, []*ast.File{file}, info, true)
	sp.Build()

	c := newCompilerContext("p2-scalar-proof", machine, cfg, false)
	defer c.ctx.Dispose()
	defer c.mod.Dispose()
	defer c.targetData.Dispose()
	c.pkg = pkg
	c.program = program
	c.packageDir = filepath.Dir(source)
	// c.runtimePkg deliberately remains nil: these functions need no runtime.
	irb := c.ctx.NewBuilder()
	defer irb.Dispose()
	for _, name := range selected {
		fn := sp.Func(name)
		if fn == nil || len(fn.Blocks) != 1 || len(fn.FreeVars) != 0 {
			t.Fatalf("%s is not a straight-line scalar leaf", name)
		}
		sig := fn.Signature
		if sig.Params().Len() != 2 || sig.Results().Len() != 1 || sig.Variadic() {
			t.Fatalf("%s: want (uint32,uint32) uint32", name)
		}
		for i := 0; i < 2; i++ {
			if !types.Identical(sig.Params().At(i).Type(), types.Typ[types.Uint32]) {
				t.Fatalf("%s: non-uint32 parameter", name)
			}
		}
		if !types.Identical(sig.Results().At(0).Type(), types.Typ[types.Uint32]) {
			t.Fatalf("%s: non-uint32 result", name)
		}
		for _, block := range fn.Blocks {
			for _, instr := range block.Instrs {
				switch instr := instr.(type) {
				case *ssa.BinOp:
					switch instr.Op {
					case token.ADD, token.SUB, token.XOR, token.OR, token.AND, token.SHL, token.SHR:
					default:
						t.Fatalf("unsupported scalar operator: %v", instr.Op)
					}
					if !types.Identical(instr.Type(), types.Typ[types.Uint32]) {
						t.Fatal("only uint32 arithmetic accepted")
					}
					if instr.Op == token.SHL || instr.Op == token.SHR {
						if _, ok := instr.Y.(*ssa.Const); !ok {
							t.Fatal("only constant shift counts accepted")
						}
					}
				case *ssa.Return, *ssa.DebugRef:
				default:
					t.Fatalf("runtime/control-flow SSA prohibited: %T (%v)", instr, instr)
				}
			}
		}
		finfo := c.getFunctionInfo(fn)
		if !finfo.exported || finfo.linkName != expected[name] {
			t.Fatalf("%s needs //export %s to use the C ABI without a closure parameter", name, expected[name])
		}
		b := newBuilder(c, irb, fn)
		b.createFunction()
		b.llvmFn.AddFunctionAttr(c.ctx.CreateStringAttribute("no-jump-tables", "true"))
		if len(b.llvmFn.Params()) != 2 {
			t.Fatal("unexpected hidden ABI parameter")
		}
	}
	for _, diagnostic := range c.diagnostics {
		t.Error(diagnostic)
	}
	if t.Failed() {
		return
	}
	count := 0
	for fn := c.mod.FirstFunction(); !fn.IsNil(); fn = llvm.NextFunction(fn) {
		count++
		if fn.IsDeclaration() {
			t.Fatalf("unexpected external dependency %s", fn.Name())
		}
		if fn.Name() != "p2_add" && fn.Name() != "p2_mix" {
			t.Fatalf("unexpected function %s", fn.Name())
		}
	}
	if count != len(selected) {
		t.Fatalf("wanted %d functions, got %d", len(selected), count)
	}
	if err := llvm.VerifyModule(c.mod, llvm.ReturnStatusAction); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(out, 0755); err != nil {
		t.Fatal(err)
	}
	artifactHashes := map[string]string{}
	// Keep the real TinyGo-generated IR even when subsequent P2 codegen fails.
	if err := ioutil.WriteFile(filepath.Join(out, "go.ll"), []byte(c.mod.String()), 0644); err != nil {
		t.Fatal(err)
	}
	irHash := sha256.Sum256([]byte(c.mod.String()))
	artifactHashes["go.ll"] = hex.EncodeToString(irHash[:])
	for _, output := range []struct {
		name string
		kind llvm.CodeGenFileType
	}{
		{"go.o", llvm.ObjectFile}, {"go.s", llvm.AssemblyFile},
	} {
		buf, err := machine.EmitToMemoryBuffer(c.mod, output.kind)
		if err != nil {
			t.Fatal(err)
		}
		data := append([]byte(nil), buf.Bytes()...)
		buf.Dispose()
		artifactHash := sha256.Sum256(data)
		artifactHashes[output.name] = hex.EncodeToString(artifactHash[:])
		if err := ioutil.WriteFile(filepath.Join(out, output.name), data, 0644); err != nil {
			t.Fatal(err)
		}
	}
	sum := sha256.Sum256(contents)
	manifest := map[string]interface{}{
		"schema": 1, "status": "OBJECT_EMITTED_NOT_HARDWARE_VALIDATED",
		"artifacts_sha256": artifactHashes,
		"tinygo":           "v0.23.0", "llvm": llvm.Version, "host_go": runtime.Version(),
		"target": "p2", "data_layout": layout,
		"source_sha256": hex.EncodeToString(sum[:]),
		"exports":       exports,
		"stage":         stage,
		"scope":         "Selected scalar leaves only. No Go main, initialization, runtime, GC, scheduler or machine package.",
	}
	encoded, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	if err := ioutil.WriteFile(filepath.Join(out, "probe.json"), append(encoded, '\n'), 0644); err != nil {
		t.Fatal(err)
	}
}
