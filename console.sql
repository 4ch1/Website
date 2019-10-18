CREATE TABLE if not exists clients
(
  email        varchar(45) primary key,
  password     varchar(12) not null,
  first_name   varchar(45) not null,
  last_name    varchar(45) not null,
  address      varchar(45) not null,
  access_level tinyint     not null
);

CREATE TABLE if not exists airports
(
  full_name  varchar(45) not null,
  short_name varchar(3) PRIMARY KEY,
  location   varchar(45) not null
);

CREATE TABLE if not exists companies
(
  full_name  varchar(45) primary key,
  short_name varchar(5)
);

create table if not exists employees
(
  email        varchar(45) primary key references clients (email),
  company_name varchar(45) references companies (full_name)
);

create table if not exists categories
(
  full_name  varchar(45) primary key,
  short_name varchar(45)
);

CREATE TABLE if not exists tickets
(
  id                 bigint primary key auto_increment,
  from_airport_short varchar(3) references airports (short_name) on delete cascade on update cascade,
  to_airport_short   varchar(3) references airports (short_name) on delete cascade on update cascade,
  date               datetime      not null,
  price              double(10, 2) not null,
  company            varchar(45) references companies (full_name),
  category           varchar(45) references categories (full_name)
);

insert into categories
values ('Business class', 'Business');

insert into categories
values ('Economy class', 'Economy');

insert into companies
values ('Czech flights', 'CZF');

insert into companies
values ('German flights', 'GEF');

insert into companies
values ('Polish flights', 'POF');

insert into companies
values ('Austrian flights', 'AUF');

insert into airports values ('Prague Ruzyne','PRG','Prague');
insert into airports values ('Berlin Ruzyne','BER','Berlin');
insert into airports values ('Bratislava Ruzyne','BRA','Bratislava');

insert into tickets values (null,'PRG','BER','2018-12-04 12:00:12',56.52,'Czech flights','Business class');
insert into tickets values (null,'PRG','BER','2018-12-04 12:40:12',34.52,'German flights','Economy class');
insert into tickets values (null,'PRG','BRA','2018-12-06 12:00:12',20.20,'Polish flights','Business class');

insert into clients values ('moderator@iis.eu','1','Moderator','Project','Kolejni 2',1);
insert into employees values ('moderator@iis.eu','Czech flights');
