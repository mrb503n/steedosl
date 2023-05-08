package cmd

import (
	"fmt"
	"github.com/spf13/cobra"
	"os"
)

func NewCmdDef() *cobra.Command {
	msgUse := fmt.Sprintf("def")
	msgShort := fmt.Sprintf("manage project definition")
	msgLong := fmt.Sprintf(`manage project definition in dory-core server`)
	msgExample := fmt.Sprintf(`  # get project build modules definition
  doryctl def get test-project1 build`)

	cmd := &cobra.Command{
		Use:                   msgUse,
		DisableFlagsInUseLine: true,
		Short:                 msgShort,
		Long:                  msgLong,
		Example:               msgExample,
		Run: func(cmd *cobra.Command, args []string) {
			if len(args) == 0 {
				cmd.Help()
				os.Exit(0)
			}
		},
	}

	cmd.AddCommand(NewCmdDefGet())
	cmd.AddCommand(NewCmdDefApply())
	return cmd
}
