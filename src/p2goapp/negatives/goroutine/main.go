// Scheduler negative: this must be rejected by TinyGo's scheduler=none path.
package main

var live uint32

func worker(v uint32) { live = v + 1 }

func main() {
	go worker(41)
	for { }
}
