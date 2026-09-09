package loader

// This target-scoped diagnostic records the actual PackageJSON stream consumed
// by loader.Load. It deliberately records SFiles separately: this TinyGo
// loader parses only GoFiles and CgoFiles (see Package.parseFiles), so listed
// assembly is not silently mistaken for parsed Go input.

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
)

type p2SelectionFile struct {
	Kind   string `json:"kind"`
	Path   string `json:"path"`
	SHA256 string `json:"sha256"`
	Bytes  int64  `json:"bytes"`
}

type p2SelectionPackage struct {
	ImportPath string            `json:"import_path"`
	Dir        string            `json:"dir"`
	Parsed     []p2SelectionFile `json:"parsed_go_or_cgo"`
	IgnoredAsm []p2SelectionFile `json:"ignored_go_assembly"`
	CFiles     []p2SelectionFile `json:"listed_c_files"`
}

func p2TraceFile(dir, kind, name string) (p2SelectionFile, error) {
	path := name
	if !filepath.IsAbs(path) {
		path = filepath.Join(dir, path)
	}
	b, err := os.ReadFile(path)
	if err != nil {
		return p2SelectionFile{}, err
	}
	sum := sha256.Sum256(b)
	return p2SelectionFile{Kind: kind, Path: path, SHA256: hex.EncodeToString(sum[:]), Bytes: int64(len(b))}, nil
}

func (p *Program) writeP2SelectionTrace() error {
	out := os.Getenv("TINYGO_P2_SELECTION_TRACE")
	if out == "" {
		return nil
	}
	isP2 := false
	for _, tag := range p.config.BuildTags() {
		if tag == "p2" {
			isP2 = true
		}
	}
	if !isP2 {
		return fmt.Errorf("TINYGO_P2_SELECTION_TRACE requires the p2 build tag")
	}
	r := struct {
		Schema       string               `json:"schema"`
		Target       string               `json:"llvm_target"`
		GOOS         string               `json:"goos"`
		GOARCH       string               `json:"goarch"`
		BuildTags    []string             `json:"build_tags"`
		LoaderPolicy string               `json:"loader_policy"`
		Packages     []p2SelectionPackage `json:"packages"`
	}{"tinygo-p2-effective-loader-selection-v1", p.config.Triple(), p.config.GOOS(), p.config.GOARCH(), p.config.BuildTags(), "loader parses GoFiles and CgoFiles only; SFiles are recorded as ignored and are not parsed/lowered by loader", nil}
	for _, pkg := range p.sorted {
		x := p2SelectionPackage{ImportPath: pkg.ImportPath, Dir: pkg.Dir}
		for _, item := range []struct {
			kind  string
			names []string
		}{{"GoFiles", pkg.GoFiles}, {"CgoFiles", pkg.CgoFiles}} {
			for _, name := range item.names {
				f, err := p2TraceFile(pkg.Dir, item.kind, name)
				if err != nil {
					return err
				}
				x.Parsed = append(x.Parsed, f)
			}
		}
		for _, name := range pkg.SFiles {
			f, err := p2TraceFile(pkg.Dir, "SFiles", name)
			if err != nil {
				return err
			}
			x.IgnoredAsm = append(x.IgnoredAsm, f)
		}
		for _, name := range pkg.CFiles {
			f, err := p2TraceFile(pkg.Dir, "CFiles", name)
			if err != nil {
				return err
			}
			x.CFiles = append(x.CFiles, f)
		}
		r.Packages = append(r.Packages, x)
	}
	sort.Slice(r.Packages, func(i, j int) bool { return r.Packages[i].ImportPath < r.Packages[j].ImportPath })
	b, err := json.MarshalIndent(r, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(out, append(b, '\n'), 0644)
}
