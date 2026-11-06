module Ex200
  class AttachHyperVLabAdapter
    def initialize(app, _env)
      @app = app
    end

    def call(env)
      machine = env[:machine]
      if machine.provider_name == :hyperv
        script = File.expand_path("hyperv_lab_network.ps1", __dir__)
        result = Vagrant::Util::Subprocess.execute(
          "powershell.exe",
          "-NoProfile",
          "-NonInteractive",
          "-ExecutionPolicy",
          "Bypass",
          "-File",
          script,
          "-VMId",
          machine.id.to_s
        )
        unless result.exit_code == 0
          raise Vagrant::Errors::VagrantError,
            "Unable to attach the Hyper-V lab network adapter: #{result.stderr}"
        end
      end

      @app.call(env)
    end
  end

  class HyperVLabNetwork < Vagrant.plugin("2")
    name "ex200-hyperv-lab-network"

    action_hook(:attach_hyperv_lab_adapter, :machine_action_up) do |hook|
      hook.before VagrantPlugins::HyperV::Action::StartInstance, AttachHyperVLabAdapter
    end
  end
end
