# Gate 2E serial protocol (version `P2E 1`)

The Go application emits these boot lines, in order:

1. `P2 PHASE2 IMPORT INIT`
2. `P2 PHASE2 INIT`
3. `READY P2E 1`

A request is exactly 37 ASCII bytes before CR or LF:

```
C iiiiiiii aaaaaaaa bbbbbbbb nnnnnnnn
```

Each field is eight hexadecimal digits (case-insensitive): opaque request ID,
`a`, `b`, and loop bound `n`. Go responds to every valid request with:

```
R E iiiiiiii vvvvvvvv ssssssss cccccccc
```

`v` is the Go challenge result, `s` is the post-update running sum and `c` is
the post-update count. All arithmetic is modulo 2^32. `n` executes `(n & 15)+1`
rounds. Any malformed or oversized line produces exactly `ERR INPUT` and leaves
challenge state unchanged. C supplies only smart-pin TX/RX byte primitives.
