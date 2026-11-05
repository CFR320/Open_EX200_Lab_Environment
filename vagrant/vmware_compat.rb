module Ex200
  class NormalizeVMwareDiskVMX
    def initialize(app, _env)
      @app = app
    end

    def call(env)
      machine = env[:machine]
      if machine.provider_name == :vmware_desktop && machine.name.to_s == "node2"
        machine.provider.driver.vmx_modify do |vmx|
          vmx.delete("scsi0:0.redo") if vmx["scsi0:0.redo"] == ""
        end
      end

      @app.call(env)
    end
  end

  class VMwareDiskCompatibility < Vagrant.plugin("2")
    name "ex200-vmware-disk-compatibility"

    action_hook(:normalize_vmware_disk_vmx, :machine_action_up) do |hook|
      hook.before Vagrant::Action::Builtin::Disk, NormalizeVMwareDiskVMX
    end
  end
end
