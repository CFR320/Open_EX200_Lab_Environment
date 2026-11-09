require "digest"
require_relative "vagrant/vmware_compat"
require_relative "vagrant/hyperv_network"

vbox_vrde_enabled = ENV["EX200_VBOX_VRDE"] == "1"
vbox_vrde_password = ENV["EX200_VBOX_VRDE_PASSWORD"]
if vbox_vrde_enabled
  unless vbox_vrde_password && vbox_vrde_password.length >= 12
    raise "EX200_VBOX_VRDE_PASSWORD must contain at least 12 characters."
  end
end

vmware_vnc_password = "Ex200Vnc"

Vagrant.configure("2") do |config|
  config.vm.box = "almalinux/10"
  config.vm.boot_timeout = 900
  config.vm.synced_folder ".", "/vagrant", disabled: true

  machines = {
    "gateway" => { hostname: "gateway.lab.example.com", ip: "172.25.250.254", memory: 2048, cpus: 1, console_index: 1 },
    "node1" => { hostname: "node1.lab.example.com", ip: "172.25.250.10", memory: 3072, cpus: 2, console_index: 2 },
    "node2" => { hostname: "node2.lab.example.com", ip: "172.25.250.11", memory: 3072, cpus: 2, console_index: 3 }
  }

  machines.each do |name, settings|
    config.vm.define name, primary: name == "gateway" do |machine|
      machine.vm.hostname = settings[:hostname]
      machine.vm.network "private_network",
        ip: settings[:ip],
        netmask: "255.255.255.0",
        bridge: "Default Switch",
        virtualbox__intnet: "ex200-lab"

      machine.vm.provider "virtualbox" do |provider|
        provider.memory = settings[:memory]
        provider.cpus = settings[:cpus]
        if vbox_vrde_enabled
          provider.customize [
            "modifyvm", :id,
            "--vrde", "on",
            "--vrde-address", ENV.fetch("EX200_VBOX_VRDE_ADDRESS", "127.0.0.1"),
            "--vrde-port", (5100 + settings[:console_index]).to_s,
            "--vrde-auth-type", "external",
            "--vrde-auth-library", "VBoxAuthSimple"
          ]
          provider.customize [
            "setextradata", :id,
            "VBoxAuthSimple/users/ex200",
            Digest::SHA256.hexdigest(vbox_vrde_password)
          ]
        else
          provider.customize ["modifyvm", :id, "--vrde", "off"]
        end
      end

      machine.vm.provider "vmware_desktop" do |provider|
        provider.vmx["virtualhw.version"] = "19"
        provider.vmx["memsize"] = settings[:memory].to_s
        provider.vmx["numvcpus"] = settings[:cpus].to_s
        provider.vmx["RemoteDisplay.vnc.enabled"] = "TRUE"
        provider.vmx["RemoteDisplay.vnc.ip"] = "127.0.0.1"
        provider.vmx["RemoteDisplay.vnc.port"] = (5900 + settings[:console_index]).to_s
        provider.vmx["RemoteDisplay.vnc.password"] = vmware_vnc_password
      end

      machine.vm.provider "hyperv" do |provider|
        provider.memory = settings[:memory]
        provider.cpus = settings[:cpus]
      end

      if name == "gateway"
        machine.vm.provision "file",
          source: "provision/lab-interface.sh",
          destination: "/tmp/ex200-lab-interface.sh"
        machine.vm.provision "file",
          source: "gateway/containers/Containerfile",
          destination: "/tmp/ex200-Containerfile"
        machine.vm.provision "file",
          source: "gateway/containers/worker.py",
          destination: "/tmp/ex200-worker.py"
        machine.vm.provision "shell", path: "gateway/provision.sh"
      else
        machine.vm.provision "file",
          source: "provision/lab-interface.sh",
          destination: "/tmp/ex200-lab-interface.sh"
        machine.vm.provision "shell",
          name: "lab-network",
          path: "provision/lab-network.sh",
          run: "always"
        machine.vm.provision "shell", name: "base", path: "provision/base.sh"
        machine.vm.provision "shell",
          name: "lab-access",
          path: "provision/lab-access.sh",
          run: "always"
        if name == "node2"
          machine.vm.provision "shell",
            name: "grub-recovery",
            path: "provision/grub-recovery.sh",
            run: "always"
        end
        machine.vm.disk :disk, size: "2GB", name: "practice-data" if name == "node2"
      end
    end
  end
end
