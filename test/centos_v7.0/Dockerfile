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
    make \
    openssl \
    openssl-devel \
    curl-devel \
    expat-devel \
    gettext-devel \
    zlib-devel \
    perl-ExtUtils-MakeMaker \
    nscd \
    curl \
    wget \
    && yum clean all \
    && rm -rf /var/cache/yum

# Compile and install git from source (2.20.1 is compatible with CentOS 7's GCC 4.8.5)
RUN cd /tmp \
    && wget https://mirrors.edge.kernel.org/pub/software/scm/git/git-2.20.1.tar.gz \
    && tar xzf git-2.20.1.tar.gz \
    && cd git-2.20.1 \
    && make prefix=/usr/local all \
    && make prefix=/usr/local install \
    && cd / \
    && rm -rf /tmp/git-*

