drop table if exists logs;
create table logs (
  id INTEGER primary key autoincrement,
  Processus TEXT NOT NULL,
  Type TEXT NOT NULL,
  Path TEXT NOT NULL,
  date_created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


drop table if exists reports;
create table reports (
  id INTEGER primary key autoincrement,
  clusters TEXT not null,
  log_id INTEGER,
  length INTEGER,
  params TEXT not null,
  date_created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(log_id) REFERENCES logs(id)
);


drop table if exists profiles;
create table profiles (
  id INTEGER primary key autoincrement,
  name TEXT not null,
  params TEXT not null,
  date_created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


drop table if exists statistics;
create table statistics (
  id INTEGER primary key autoincrement,
  log_id INTEGER,
  params TEXT not null,
  date_created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(log_id) REFERENCES logs(id)

);

insert into logs (Processus,Type, Path) values ("RDM","INFO","/home/hamza/Desktop/projet_s5/project files/data_in/rdm-coherence.log");
/*insert into statistics (log_id,params) values (1,"RDM");
SELECT * FROM logs;
SELECT * FROM reports;
SELECT * FROM statistics;
*/
