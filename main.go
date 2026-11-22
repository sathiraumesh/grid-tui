package main

import (
	"fmt"
	"os"

	"grid-tui/app"
)

// version is the release the binary was built from, set by the release
// build: go build -ldflags "-X main.version=v1.2.3".
var version = "dev"

func main() {
	if len(os.Args) > 1 && (os.Args[1] == "--version" || os.Args[1] == "-v") {
		fmt.Println("grid-tui", version)
		return
	}
	if err := app.New().Run(); err != nil {
		fmt.Println("error:", err)
		os.Exit(1)
	}
}
