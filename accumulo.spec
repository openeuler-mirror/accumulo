%global _hardened_build 1
%global longproj Apache Accumulo

# jpackage main class
%global main_class org.apache.%{name}.start.Main

Name:    accumulo
Version: 2.0.1
Release: 1
Summary: A software platform for processing vast amounts of data
License: Apache-2.0 and  BSD
Group:   Development/Libraries
URL:     https://github.com/apache/%{name}/
Source0: https://github.com/apache/%{name}/archive/refs/tags/%{version}.tar.gz
Source1: %{name}-master.service
Source2: %{name}-tserver.service
Source3: %{name}-gc.service
Source4: %{name}-tracer.service
Source5: %{name}-monitor.service
Source6: %{name}.conf
Source7: xmvn-reactor
Source8: accumulo-metrics.xml
Source9: auditLog.xml

Patch0:  0001-add-dependent-package-to-lib.patch

BuildRequires: java-1.8.0-openjdk-devel maven maven-local
Requires: java-1.8.0-openjdk
Requires(pre): /usr/sbin/useradd
Requires: apache-commons-cli apache-commons-codec apache-commons-collections apache-commons-configuration
Requires: apache-commons-dbcp apache-commons-daemon apache-commons-io apache-commons-lang apache-commons-logging
Requires: apache-commons-math apache-commons-pool apache-commons-vfs avro beust-jcommander dnf
Requires: glassfish-servlet-api guava google-gson jansi jetty jline nodejs-flot protobuf-java slf4j zookeeper
Requires(post): systemd-units
Requires(preun): systemd-units
Requires(postun): systemd-units

%description
  %{longproj} is a sorted, distributed key/value store based on Google's
BigTable design. It is built on top of Apache Hadoop, Zookeeper, and Thrift. It
features a few novel improvements on the BigTable design in the form of
cell-level access labels and a server-side programming mechanism that can
modify key/value pairs at various points in the data management process.

%prep
%autosetup -p1 -n %{name}-rel-%{version}
# Remove flot and jquery bundling from upstream tarball
rm -rf server/monitor/src/main/resources/web/flot/

%pom_remove_plugin :apache-rat-plugin 

cp %{SOURCE7} ./.xmvn-reactor
echo `pwd` > absolute_prefix.log
sed -i 's/\//\\\//g' absolute_prefix.log
absolute_prefix=`head -n 1 absolute_prefix.log`
sed -i 's/absolute-prefix/'"$absolute_prefix"'/g' .xmvn-reactor

find -name "*.jar" -delete
find -name "*.cmd" -delete

%build
# TODO Unit tests are skipped, because upstream tries to do some integration
# testing in the unit tests, and they expect certain resources and dependencies
# that are not typically available, or are too complicated to configure,
# especially in the start jar. These should be enabled when possible.
# ITs are skipped, because they time out frequently and take too many resources
# to run reliably. Failures do not reliably indicate meaningful issues.
mvn package -DforkCount=1C -DskipTests -DskipITs -Dtaro

%install
install -d -m 755 %{buildroot}%{_datadir}/java/%{name}
%mvn_install
cp -arf target/lib/* %{buildroot}%{_datadir}/java/%{name}
cp %{SOURCE8} assemble/bin

# create symlink for system-provided web assets to be added to classpath
install -d -m 755 %{buildroot}%{_datadir}/%{name}/lib/web
rm -f %{buildroot}%{_datadir}/%{name}/lib/web/flot
ln -s %{_usr}/lib/node_modules/flot %{buildroot}%{_datadir}/%{name}/lib/web/flot

# native libs
install -d -m 755 %{buildroot}%{_libdir}/%{name}
install -d -m 755 %{buildroot}%{_var}/cache/%{name}
install -p -m 755 server/native/target/%{name}-native-%{version}/%{name}-native-%{version}/lib%{name}.so %{buildroot}%{_libdir}/%{name}
ln -s %{_libdir}/%{name}/lib%{name}.so %{buildroot}%{_prefix}/lib/
# generate default config for Fedora from upstream examples
install -d -m 755 %{buildroot}%{_sysconfdir}/%{name}
install -d -m 755 %{buildroot}%{_sysconfdir}/%{name}/lib
install -d -m 755 %{buildroot}%{_sysconfdir}/%{name}/lib/ext
cp -arf assemble/conf/* %{buildroot}%{_sysconfdir}/%{name}/
cp assemble/conf/templates/hadoop-metrics2-accumulo.properties %{buildroot}%{_sysconfdir}/%{name}/
rm -rf  %{buildroot}%{_sysconfdir}/%{name}/templates
for x in gc masters monitor slaves tracers %{name}-env.sh generic_logger.xml generic_logger.properties monitor_logger.xml monitor_logger.properties %{name}.policy.example; do rm -f %{buildroot}%{_sysconfdir}/%{name}/$x; done
cp %{buildroot}%{_sysconfdir}/%{name}/log4j.properties %{buildroot}%{_sysconfdir}/%{name}/generic_logger.properties
cp %{buildroot}%{_sysconfdir}/%{name}/log4j.properties %{buildroot}%{_sysconfdir}/%{name}/monitor_logger.properties
cp %{SOURCE8} %{buildroot}%{_sysconfdir}/%{name}
cp %{SOURCE9} %{buildroot}%{_sysconfdir}/%{name}

# main launcher
%jpackage_script %{main_class} "" "" %{name}:%{name}/%{name}-tserver:jetty:servlet:avro/avro:apache-commons-io:apache-commons-cli:apache-commons-codec:apache-commons-collections:apache-commons-configuration:apache-commons-lang:apache-commons-logging:apache-commons-math:apache-commons-vfs:beust-jcommander:google-gson:guava:hadoop/hadoop-auth:hadoop/hadoop-common:hadoop/hadoop-hdfs:jansi/jansi:jline/jline:libthrift:log4j-1.2.17:slf4j/slf4j-api:slf4j/slf4j-log4j12:zookeeper/zookeeper:protobuf-java %{name} true
# fixup the generated jpackage script
sed -i -e 's/^#!\/bin\/sh$/#!\/usr\/bin\/bash/' %{buildroot}%{_bindir}/%{name}
# ensure the java configuration options know which service is being called
sed -i -e 's/^\s*\.\s\s*\/etc\/java\/'%{name}'\.conf/& "\$1"/' %{buildroot}%{_bindir}/%{name}
sed -i -e 's/^\s*\.\s\s*\$HOME\/\.'%{name}'rc$/& "\$1"/' %{buildroot}%{_bindir}/%{name}
# options may have spaces in them, so replace run with an exec that properly
# parses arguments as arrays.
sed -i -e '/^run .*$/d' %{buildroot}%{_bindir}/%{name}
sed -i -e '/^set_flags .*$/d' %{buildroot}%{_bindir}/%{name}
sed -i -e '/^set_options .*$/d' %{buildroot}%{_bindir}/%{name}
cat <<EOF >>%{buildroot}%{_bindir}/%{name}
CLASSPATH="%{_sysconfdir}/%{name}:%{_datadir}/%{name}/lib/:\${CLASSPATH}"
set_javacmd

if [ -n "\${VERBOSE}" ]; then
  echo "Java virtual machine used: \${JAVACMD}"
  echo "classpath used: \${CLASSPATH}"
  echo "main class used: \${MAIN_CLASS}"
  echo "flags used: \${FLAGS[*]}"
  echo "options used: \${ACCUMULO_OPTS[*]}"
  echo "arguments used: \${*}"
fi

export CLASSPATH
exec "\${JAVACMD}" "\${FLAGS[@]}" "\${ACCUMULO_OPTS[@]}" "\${MAIN_CLASS}" "\${@}"
EOF

# scripts for services/utilities
for service in master tserver shell init admin gc tracer classpath version rfile-info login-info zookeeper create-token info jar; do
  cat <<EOF >"%{name}-$service"
#!/usr/bin/bash
echo "%{name}-$service script is deprecated. Use '%{name} $service' instead." 1>&2
%{_bindir}/%{name} $service "\$@"
EOF
  install -p -m 755 %{name}-$service %{buildroot}%{_bindir}
done

# systemd services
install -d -m 755 %{buildroot}%{_unitdir}
install -p -m 644 %{SOURCE1} %{buildroot}%{_unitdir}/%{name}-master.service
install -p -m 644 %{SOURCE2} %{buildroot}%{_unitdir}/%{name}-tserver.service
install -p -m 644 %{SOURCE3} %{buildroot}%{_unitdir}/%{name}-gc.service
install -p -m 644 %{SOURCE4} %{buildroot}%{_unitdir}/%{name}-tracer.service
install -p -m 644 %{SOURCE5} %{buildroot}%{_unitdir}/%{name}-monitor.service

# java configuration file for Fedora
install -d -m 755 %{buildroot}%{_javaconfdir}
install -p -m 755 %{SOURCE6} %{buildroot}%{_javaconfdir}/%{name}.conf

#fix absence
install -d -m 755 %{buildroot}%{_datadir}/doc/%{name}/
install -p -m 644 README.md %{buildroot}%{_datadir}/doc/%{name}/

%files -f .mfiles
%doc LICENSE
%doc README.md
%doc NOTICE
%dir %{_javadir}/%{name}
%dir %{_mavenpomdir}/%{name}
%dir %{_datadir}/%{name}
%dir %{_datadir}/%{name}/lib
%{_javadir}/%{name}/*
%{_bindir}/%{name}
%{_bindir}/%{name}-shell
%{_bindir}/%{name}-classpath
%{_bindir}/%{name}-version
%{_bindir}/%{name}-rfile-info
%{_bindir}/%{name}-login-info
%{_bindir}/%{name}-zookeeper
%{_bindir}/%{name}-create-token
%{_bindir}/%{name}-info
%{_bindir}/%{name}-jar
%attr(0750, %{name}, -) %dir %{_var}/cache/%{name}
%attr(0755, %{name}, -) %dir %{_sysconfdir}/%{name}
%attr(0755, %{name}, -) %dir %{_sysconfdir}/%{name}/lib
%attr(0755, %{name}, -) %dir %{_sysconfdir}/%{name}/lib/ext
%attr(0755, %{name}, -) %config(noreplace) %{_javaconfdir}/%{name}.conf
%attr(0640, %{name}, -) %config(noreplace) %{_sysconfdir}/%{name}/%{name}-metrics.xml
%attr(0640, %{name}, -) %config(noreplace) %{_sysconfdir}/%{name}/auditLog.xml
%attr(0640, %{name}, -) %config(noreplace) %{_sysconfdir}/%{name}/generic_logger.properties
%attr(0644, %{name}, -) %config(noreplace) %{_sysconfdir}/%{name}/log4j.properties
%attr(0640, %{name}, -) %config(noreplace) %{_sysconfdir}/%{name}/monitor_logger.properties
%attr(0640, %{name}, -) %config(noreplace) %{_sysconfdir}/%{name}/hadoop-metrics2-accumulo.properties
%attr(0640, %{name}, -) %config(noreplace) %{_sysconfdir}/%{name}/log4j-monitor.properties
%attr(0640, %{name}, -) %config(noreplace) %{_sysconfdir}/%{name}/log4j-service.properties
%attr(0640, %{name}, -) %config(noreplace) %{_sysconfdir}/%{name}/accumulo.properties
%{_bindir}/%{name}-init
%{_bindir}/%{name}-admin
%{_bindir}/%{name}-master
%{_unitdir}/%{name}-master.service
%dir %{_jnidir}/%{name}
%{_bindir}/%{name}-tserver
%{_unitdir}/%{name}-tserver.service
%{_bindir}/%{name}-gc
%{_unitdir}/%{name}-gc.service
%dir %{_datadir}/%{name}/lib/web
%{_datadir}/%{name}/lib/web/flot
%{_unitdir}/%{name}-monitor.service
%{_bindir}/%{name}-tracer
%{_unitdir}/%{name}-tracer.service
%dir %{_libdir}/%{name}
%{_libdir}/%{name}/lib%{name}.so
%{_prefix}/lib/lib%{name}.so

%preun 
%systemd_preun %{name}-master.service
%systemd_preun %{name}-tserver.service
%systemd_preun %{name}-gc.service
%systemd_preun %{name}-tracer.service
%systemd_preun %{name}-monitor.service

%postun
%systemd_postun_with_restart %{name}-master.service
%systemd_postun_with_restart %{name}-tserver.service
%systemd_postun_with_restart %{name}-gc.service
%systemd_postun_with_restart %{name}-tracer.service
%systemd_postun_with_restart %{name}-monitor.service

%pre 
getent group %{name} >/dev/null || /usr/sbin/groupadd -r %{name}
getent passwd %{name} >/dev/null || /usr/sbin/useradd --comment "%{longproj}" --shell /sbin/nologin -M -r -g %{name} --home %{_var}/cache/%{name} %{name}

%post 
%systemd_post %{name}-master.service
%systemd_post %{name}-tserver.service
%systemd_post %{name}-gc.service
%systemd_post %{name}-tracer.service
%systemd_post %{name}-monitor.service
hadoop_info=`dnf list installed | grep hadoop`
if [ -z ${hadoop_info} ];then
  echo "WARNING: Package hadoop or hadoop-3.1 should be installed first"
fi

%changelog
* Mon Jun 21 2021 Ge Wang <wangge20@huawei> - 2.0.1-1
- Initial packaging
