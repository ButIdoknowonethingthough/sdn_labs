# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
  config.vm.define "sdn-controller" do |controller|
    controller.vm.box = "ubuntu/jammy64"
    controller.vm.hostname = "sdn-controller"
    controller.vm.network "private_network", ip: "192.168.56.10"
    
    controller.vm.provider "virtualbox" do |vb|
      vb.memory = "4096"
      vb.cpus = 2
    end  
    
    controller.vm.provision "shell", path: "controller.sh"
  end  # Закрываем блок sdn-controller
  
  config.vm.define "mininet-host" do |mininet|
    mininet.vm.box = "ubuntu/jammy64"
    mininet.vm.hostname = "mininet-host"
    mininet.vm.network "private_network", ip: "192.168.56.20"
    
    mininet.vm.provider "virtualbox" do |vb|
      vb.memory = "4096"  # Mininet требует больше ресурсов
      vb.cpus = 2
    end  
    mininet.vm.provision "shell", path: "mininet.sh"
  end  
end
