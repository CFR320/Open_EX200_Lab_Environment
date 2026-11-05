require_relative "vagrant/vmware_compat"

Vagrant.configure("2") do |config|
  config.vm.box = "bento/rockylinux-10"
  config.vm.boot_timeout = 900
  config.vm.synced_folder ".", "/vagrant", disabled: true

  machines = {
    "gateway" => { hostname: "gateway.lab.example.com", ip: "172.25.250.254", memory: 2048, cpus: 1 },
    "node1" => { hostname: "node1.lab.example.com", ip: "172.25.250.10", memory: 3072, cpus: 2 },
    "node2" => { hostname: "node2.lab.example.com", ip: "172.25.250.11", memory: 3072, cpus: 2 }
  }

  machines.each do |name, settings|
    config.vm.define name, primary: name == "gateway" do |machine|
      machine.vm.hostname = settings[:hostname]
      machine.vm.network "private_network",
        ip: settings[:ip],
        netmask: "255.255.255.0",
        virtualbox__intnet: "ex200-lab"

      machine.vm.provider "virtualbox" do |provider|
        provider.memory = settings[:memory]
        provider.cpus = settings[:cpus]
      end

      machine.vm.provider "vmware_desktop" do |provider|
        provider.vmx["virtualhw.version"] = "19"
        provider.vmx["memsize"] = settings[:memory].to_s
        provider.vmx["numvcpus"] = settings[:cpus].to_s
      end

      machine.vm.provider "hyperv" do |provider|
        provider.memory = settings[:memory]
        provider.cpus = settings[:cpus]
      end

      if name == "gateway"
        machine.vm.provision "file",
          source: "gateway/containers/Containerfile",
          destination: "/tmp/ex200-Containerfile"
        machine.vm.provision "file",
          source: "gateway/containers/worker.py",
          destination: "/tmp/ex200-worker.py"
        machine.vm.provision "shell", path: "gateway/provision.sh"
      else
        machine.vm.provision "shell", name: "base", path: "provision/base.sh"
        machine.vm.provision "shell",
          name: "lab-access",
          path: "provision/lab-access.sh",
          run: "always"
        machine.vm.provision "shell",
          name: "lab-network",
          path: "provision/lab-network.sh",
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
