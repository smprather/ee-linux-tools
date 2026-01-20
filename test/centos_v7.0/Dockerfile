# GLIBC 2.27
FROM centos:7

RUN sed -i 's/mirror\.centos\.org/vault.centos.org/g' /etc/yum.repos.d/CentOS-*.repo
RUN sed -i 's/^#.*baseurl=http/baseurl=http/g' /etc/yum.repos.d/CentOS-*.repo
RUN sed -i 's/^mirrorlist=http/#mirrorlist=http/g' /etc/yum.repos.d/CentOS-*.repo

RUN yum update -y && yum install -y \
    strace \
    which \
    vim \
    gcc \
    openssl \
    nscd \
    && yum clean all \
    && rm -rf /var/cache/yum

