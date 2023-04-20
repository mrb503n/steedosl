package cmd

import (
	"encoding/json"
	"fmt"
	"github.com/dory-engine/dory-ctl/pkg"
	"github.com/olekukonko/tablewriter"
	"github.com/spf13/cobra"
	"net/http"
	"os"
	"strings"
)

type OptionsDefGet struct {
	*OptionsCommon `yaml:"optionsCommon" json:"optionsCommon" bson:"optionsCommon" validate:""`
	EnvName        string `yaml:"envName" json:"envName" bson:"envName" validate:""`
	BranchName     string `yaml:"branchName" json:"branchName" bson:"branchName" validate:""`
	StepName       string `yaml:"stepName" json:"stepName" bson:"stepName" validate:""`
	Output         string `yaml:"output" json:"output" bson:"output" validate:""`
	Param          struct {
		Kind        string   `yaml:"kind" json:"kind" bson:"kind" validate:""`
		ProjectName string   `yaml:"projectName" json:"projectName" bson:"projectName" validate:""`
		ModuleNames []string `yaml:"moduleNames" json:"moduleNames" bson:"moduleNames" validate:""`
	}
}

func NewOptionsDefGet() *OptionsDefGet {
	var o OptionsDefGet
	o.OptionsCommon = OptCommon
	return &o
}

var kinds = []string{
	"build",
	"package",
	"deploy",
	"pipeline",
	"ignore",
	"ops",
	"step",
	"steps",
}

func NewCmdDefGet() *cobra.Command {
	o := NewOptionsDefGet()

	msgUse := fmt.Sprintf(`get [projectName] [kind] [moduleName]...
  # kind options: %s`, strings.Join(kinds, " / "))
	msgShort := fmt.Sprintf("get project definition")
	msgLong := fmt.Sprintf(`get project definition in dory-core server`)
	msgExample := fmt.Sprintf(`  # get project build modules definition
  # doryctl def get [projectName] build [moduleName]...
  doryctl def get test-project1 build tp1-go-demo tp1-gin-demo

  # get project package modules definition
  # doryctl def get [projectName] package [moduleName]...
  doryctl def get test-project1 package tp1-go-demo tp1-gin-demo -o yaml

  # get project deploy modules definition
  # doryctl def get [projectName] deploy [moduleName]... --env [envName]
  doryctl def get test-project1 deploy tp1-go-demo tp1-gin-demo --env test

  # get project pipeline definition
  # doryctl def get [projectName] pipeline --branch [branchName]
  doryctl def get test-project1 pipeline --branch develop

  # get project docker ignore definition
  # doryctl def get [projectName] ignore
  doryctl def get test-project1 ignore

  # get project custom ops batch steps definition
  # doryctl def get [projectName] ops [opsName]...
  doryctl def get test-project1 ops tp1-auto-test

  # get project custom step modules definition (environment independent custom step)
  # doryctl def get [projectName] step [moduleName]... --step [customStepName]
  doryctl def get test-project1 step tp1-go-demo --step scanCode

  # get project custom step modules definition (environment related custom step)
  # doryctl def get [projectName] step [moduleName]... --step [customStepName] --env [envName]
  doryctl def get test-project1 step tp1-go-demo --step testApi --env test

  # get project all available custom steps
  # doryctl def get [projectName] steps
  doryctl def get steps test-project1
`)

	cmd := &cobra.Command{
		Use:                   msgUse,
		DisableFlagsInUseLine: true,
		Short:                 msgShort,
		Long:                  msgLong,
		Example:               msgExample,
		Run: func(cmd *cobra.Command, args []string) {
			CheckError(o.Complete(cmd))
			CheckError(o.Validate(args))
			CheckError(o.Run(args))
		},
	}
	cmd.Flags().StringVarP(&o.Output, "output", "o", "", "output format (options: yaml / json)")
	cmd.Flags().StringVar(&o.EnvName, "env", "", "envName, required if kind is deploy")
	cmd.Flags().StringVar(&o.BranchName, "branch", "", "branchName, required if kind is pipeline")
	cmd.Flags().StringVar(&o.StepName, "step", "", "stepName, required if kind is step")
	return cmd
}

func (o *OptionsDefGet) Complete(cmd *cobra.Command) error {
	var err error
	err = o.GetOptionsCommon()
	return err
}

func (o *OptionsDefGet) Validate(args []string) error {
	var err error
	if len(args) == 0 {
		err = fmt.Errorf("projectName required")
		return err
	}
	if len(args) == 1 {
		err = fmt.Errorf("kind required")
		return err
	}
	var projectName, kind string
	var moduleNames []string
	projectName = args[0]
	kind = args[1]

	var found bool
	for _, k := range kinds {
		if k == kind {
			found = true
			break
		}
	}
	if !found {
		err = fmt.Errorf("kind must be %s", strings.Join(kinds, ","))
		return err
	}
	err = pkg.ValidateMinusNameID(projectName)
	if err != nil {
		err = fmt.Errorf("projectNames error: %s", err.Error())
		return err
	}
	if kind == "deploy" && o.EnvName == "" {
		err = fmt.Errorf("kind is deploy, --env is required")
		return err
	}
	if kind == "pipeline" && o.BranchName == "" {
		err = fmt.Errorf("kind is pipeline, --branch is required")
		return err
	}
	if kind == "step" && o.StepName == "" {
		err = fmt.Errorf("kind is step, --step is required")
		return err
	}
	moduleNames = args[2:]
	for _, moduleName := range moduleNames {
		err = pkg.ValidateMinusNameID(moduleName)
		if err != nil {
			err = fmt.Errorf("moduleName %s format error: %s", moduleName, err.Error())
			return err
		}
	}
	o.Param.Kind = kind
	o.Param.ProjectName = projectName
	o.Param.ModuleNames = moduleNames

	if o.Output != "" {
		if o.Output != "yaml" && o.Output != "json" {
			err = fmt.Errorf("--output must be yaml or json")
			return err
		}
	}
	return err
}

func (o *OptionsDefGet) Run(args []string) error {
	var err error

	bs, _ := pkg.YamlIndent(o)
	log.Debug(fmt.Sprintf("command options:\n%s", string(bs)))

	param := map[string]interface{}{}
	result, _, err := o.QueryAPI(fmt.Sprintf("api/cicd/projectDef/%s", o.Param.ProjectName), http.MethodGet, "", param, false)
	if err != nil {
		return err
	}
	project := pkg.ProjectOutput{}
	err = json.Unmarshal([]byte(result.Get("data.project").Raw), &project)
	if err != nil {
		return err
	}

	defKind := pkg.DefKind{
		Kind: "",
		Metadata: pkg.Metadata{
			Name:        project.ProjectInfo.ProjectName,
			ProjectName: project.ProjectInfo.ProjectName,
			Labels:      map[string]string{},
		},
		Items: []interface{}{},
	}
	dataOutput := map[string]interface{}{}
	dataHeader := []string{}
	dataRows := [][]string{}
	switch o.Param.Kind {
	case "build":
		defKind.Kind = "buildDefs"
		for _, def := range project.ProjectDef.BuildDefs {
			var isShow bool
			if len(o.Param.ModuleNames) == 0 {
				isShow = true
			} else {
				for _, moduleName := range o.Param.ModuleNames {
					if moduleName == def.BuildName {
						isShow = true
						break
					}
				}
			}
			if isShow {
				dataRow := []string{def.BuildName, def.BuildEnv, def.BuildPath, fmt.Sprintf("%d", def.BuildPhaseID), strings.Join(def.BuildCmds, "\n")}
				dataRows = append(dataRows, dataRow)
				defKind.Items = append(defKind.Items, def)
			}
		}
		dataHeader = []string{"Name", "Env", "Path", "PhaseID", "Cmds"}
		m := map[string]interface{}{}
		bs, _ = json.Marshal(defKind)
		_ = json.Unmarshal(bs, &m)
		dataOutput = pkg.RemoveMapEmptyItems(m)
	case "package":
		defKind.Kind = "packageDefs"
		for _, def := range project.ProjectDef.PackageDefs {
			var isShow bool
			if len(o.Param.ModuleNames) == 0 {
				isShow = true
			} else {
				for _, moduleName := range o.Param.ModuleNames {
					if moduleName == def.PackageName {
						isShow = true
						break
					}
				}
			}
			if isShow {
				dataRow := []string{def.PackageName, strings.Join(def.RelatedBuilds, "\n"), def.PackageFrom, strings.Join(def.Packages, "\n")}
				dataRows = append(dataRows, dataRow)
				defKind.Items = append(defKind.Items, def)
			}
		}
		defKind.ErrMsg = project.ProjectDef.ErrMsgPackageDefs
		dataHeader = []string{"Name", "Builds", "From", "Dockerfile"}
		m := map[string]interface{}{}
		bs, _ = json.Marshal(defKind)
		_ = json.Unmarshal(bs, &m)
		dataOutput = pkg.RemoveMapEmptyItems(m)
	case "deploy":
		defKind.Kind = "deployContainerDefs"
		projectAvailableEnv := pkg.ProjectAvailableEnv{}
		deployContainerDefs := []pkg.DeployContainerDef{}
		var found bool
		for _, pae := range project.ProjectAvailableEnvs {
			if pae.EnvName == o.EnvName {
				projectAvailableEnv = pae
				deployContainerDefs = pae.DeployContainerDefs
				found = true
				break
			}
		}
		if !found {
			err = fmt.Errorf("envName %s not exists", o.EnvName)
			return err
		}
		for _, def := range deployContainerDefs {
			var isShow bool
			if len(o.Param.ModuleNames) == 0 {
				isShow = true
			} else {
				for _, moduleName := range o.Param.ModuleNames {
					if moduleName == def.DeployName {
						isShow = true
						break
					}
				}
			}
			if isShow {
				var ports []string
				for _, p := range def.DeployLocalPorts {
					if p.Protocol == "" {
						p.Protocol = "TCP"
					}
					ports = append(ports, fmt.Sprintf("%d/%s", p.Port, p.Protocol))
				}
				for _, p := range def.DeployNodePorts {
					if p.Protocol == "" {
						p.Protocol = "TCP"
					}
					ports = append(ports, fmt.Sprintf("%d:%d/%s", p.Port, p.NodePort, p.Protocol))
				}

				dependServices := []string{}
				for _, ds := range def.DependServices {
					dependServices = append(dependServices, fmt.Sprintf("%s:%d", ds.DependName, ds.DependPort))
				}
				dataRow := []string{def.DeployName, def.RelatedPackage, fmt.Sprintf("%d", def.DeployReplicas), strings.Join(ports, ","), strings.Join(dependServices, "\n")}
				dataRows = append(dataRows, dataRow)
				defKind.Items = append(defKind.Items, def)
			}
		}
		defKind.ErrMsg = projectAvailableEnv.ErrMsgDeployContainerDefs
		defKind.Metadata.Labels = map[string]string{
			"envName": projectAvailableEnv.EnvName,
		}
		dataHeader = []string{"Name", "Package", "Replicas", "Ports", "Depends"}
		m := map[string]interface{}{}
		bs, _ = json.Marshal(defKind)
		_ = json.Unmarshal(bs, &m)
		dataOutput = pkg.RemoveMapEmptyItems(m)
	case "pipeline":
		defKind.Kind = "pipelineDef"
		pipeline := pkg.ProjectPipeline{}
		def := pkg.PipelineDef{}
		var found bool
		for _, pp := range project.ProjectPipelines {
			if pp.BranchName == o.BranchName {
				pipeline = pp
				def = pp.PipelineDef
				found = true
				break
			}
		}
		if !found {
			err = fmt.Errorf("branchName %s not exists", o.BranchName)
			return err
		}

		var builds []string
		for _, build := range def.Builds {
			buildStr := fmt.Sprintf("%s: %v", build.Name, build.Run)
			builds = append(builds, buildStr)
		}
		dataRow := []string{o.BranchName, strings.Join(pipeline.Envs, "\n"), strings.Join(pipeline.EnvProductions, "\n"), fmt.Sprintf("%v", def.IsAutoDetectBuild), fmt.Sprintf("%v", def.IsQueue), strings.Join(builds, "\n")}
		dataRows = append(dataRows, dataRow)
		defKind.Items = append(defKind.Items, def)

		defKind.ErrMsg = pipeline.ErrMsgPipelineDef
		defKind.Metadata.Labels = map[string]string{
			"branchName":     pipeline.BranchName,
			"envs":           strings.Join(pipeline.Envs, ","),
			"envProductions": strings.Join(pipeline.EnvProductions, ","),
		}
		dataHeader = []string{"Name", "Envs", "EnvProds", "AutoDetect", "Queue", "Builds"}
		m := map[string]interface{}{}
		bs, _ = json.Marshal(defKind)
		_ = json.Unmarshal(bs, &m)
		dataOutput = pkg.RemoveMapEmptyItems(m)
	case "ignore":
		defKind.Kind = "dockerIgnoreDefs"
		for _, def := range project.ProjectDef.DockerIgnoreDefs {
			dataRow := []string{def}
			dataRows = append(dataRows, dataRow)
			defKind.Items = append(defKind.Items, def)
		}
		dataHeader = []string{"Ignore"}
		m := map[string]interface{}{}
		bs, _ = json.Marshal(defKind)
		_ = json.Unmarshal(bs, &m)
		dataOutput = pkg.RemoveMapEmptyItems(m)
	case "ops":
		defKind.Kind = "customOpsDefs"
		for _, def := range project.ProjectDef.CustomOpsDefs {
			var isShow bool
			if len(o.Param.ModuleNames) == 0 {
				isShow = true
			} else {
				for _, moduleName := range o.Param.ModuleNames {
					if moduleName == def.CustomOpsName {
						isShow = true
						break
					}
				}
			}
			if isShow {
				dataRow := []string{def.CustomOpsName, def.CustomOpsDesc, strings.Join(def.CustomOpsSteps, "\n")}
				dataRows = append(dataRows, dataRow)
				defKind.Items = append(defKind.Items, def)
			}
		}
		defKind.ErrMsg = project.ProjectDef.ErrMsgCustomOpsDefs
		dataHeader = []string{"Name", "Desc", "Steps"}
		m := map[string]interface{}{}
		bs, _ = json.Marshal(defKind)
		_ = json.Unmarshal(bs, &m)
		dataOutput = pkg.RemoveMapEmptyItems(m)
	case "step":
		defKind.Kind = "customStepDefs"
		customStepDefs := map[string]pkg.CustomStepDef{}
		mapErrMsg := map[string]string{}
		if o.EnvName != "" {
			var found bool
			for _, pae := range project.ProjectAvailableEnvs {
				if pae.EnvName == o.EnvName {
					mapErrMsg = pae.ErrMsgCustomStepDefs
					customStepDefs = pae.CustomStepDefs
					found = true
					break
				}
			}
			if !found {
				err = fmt.Errorf("envName %s not exists", o.EnvName)
				return err
			}
		} else {
			mapErrMsg = project.ProjectDef.ErrMsgCustomStepDefs
			customStepDefs = project.ProjectDef.CustomStepDefs
		}

		var found bool
		var customStepDef pkg.CustomStepDef
		for stepName, def := range customStepDefs {
			if stepName == o.StepName {
				customStepDef = def
				found = true
				break
			}
		}
		if !found {
			err = fmt.Errorf("stepName %s not exists", o.StepName)
			return err
		}
		var errMsg string
		for stepName, msg := range mapErrMsg {
			if stepName == o.StepName {
				errMsg = msg
			}
		}
		for _, csmd := range customStepDef.CustomStepModuleDefs {
			var isShow bool
			if len(o.Param.ModuleNames) == 0 {
				isShow = true
			} else {
				for _, moduleName := range o.Param.ModuleNames {
					if moduleName == csmd.ModuleName {
						isShow = true
						break
					}
				}
			}
			if isShow {
				enableMode := customStepDef.EnableMode
				if enableMode == "" {
					enableMode = "manual"
				}
				dataRow := []string{csmd.ModuleName, customStepDef.EnableMode, strings.Join(csmd.RelatedStepModules, "\n"), fmt.Sprintf("%v", csmd.ManualEnable), csmd.ParamInputYaml}
				dataRows = append(dataRows, dataRow)
				defKind.Items = append(defKind.Items, csmd)
			}
		}

		defKind.ErrMsg = errMsg
		defKind.Metadata.Labels = map[string]string{
			"envName":    o.EnvName,
			"stepName":   o.StepName,
			"enableMode": customStepDef.EnableMode,
		}
		dataHeader = []string{"Name", "EnableMode", "RelateModules", "ManualEnable", "Params"}
		m := map[string]interface{}{}
		bs, _ = json.Marshal(defKind)
		_ = json.Unmarshal(bs, &m)
		dataOutput = pkg.RemoveMapEmptyItems(m)
	case "steps":
		defKind.Kind = "customStepConfs"
		for _, def := range project.CustomStepConfs {
			dataRow := []string{def.CustomStepName, def.CustomStepDesc, def.CustomStepActionDesc, fmt.Sprintf("%v", def.IsEnvDiff), def.ParamInputYamlDef}
			dataRows = append(dataRows, dataRow)
			defKind.Items = append(defKind.Items, def)
		}
		defKind.ErrMsg = project.ProjectDef.ErrMsgPackageDefs
		dataHeader = []string{"Name", "Desc", "Action", "EnvDiff", "Params"}
		m := map[string]interface{}{}
		bs, _ = json.Marshal(defKind)
		_ = json.Unmarshal(bs, &m)
		dataOutput = pkg.RemoveMapEmptyItems(m)
	}

	if defKind.ErrMsg != "" {
		log.Error(defKind.ErrMsg)
	}

	switch o.Output {
	case "json":
		bs, _ = json.MarshalIndent(dataOutput, "", "  ")
		fmt.Println(string(bs))
	case "yaml":
		bs, _ = pkg.YamlIndent(dataOutput)
		fmt.Println(string(bs))
	default:
		table := tablewriter.NewWriter(os.Stdout)
		table.SetHeader(dataHeader)
		table.SetAutoWrapText(false)
		table.SetAutoFormatHeaders(true)
		table.SetHeaderAlignment(tablewriter.ALIGN_LEFT)
		table.SetAlignment(tablewriter.ALIGN_LEFT)
		table.SetCenterSeparator("")
		table.SetColumnSeparator("")
		table.SetRowSeparator("")
		table.SetHeaderLine(false)
		table.SetBorder(false)
		table.SetTablePadding("\t")
		table.SetNoWhiteSpace(true)
		table.AppendBulk(dataRows)
		table.Render()
	}

	return err
}