using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using IIS.Models.Tickets;
using MySql.Data.MySqlClient;

namespace IIS.Queries
{
    public static class CompanyQueries
    {
        private static readonly MySqlConnection Connection = (MySqlConnection)Program.Connection.Clone();

        static CompanyQueries()
        {
            Connection.Open();
        }

        public static async Task<Company> GetByFull(string name)
        {
            var query = $"select * from companies where full_name='{DbUtils.EscapeString(name)}'";

            var command = new MySqlCommand(query, Connection);

            using (var reader = await command.ExecuteReaderAsync())
            {
                await reader.ReadAsync();
                return new Company(reader["full_name"].ToString(), reader["short_name"].ToString());

            }
        }

        public static async Task<IEnumerable<Company>> GetAll()
        {
            var retList = new List<Company>();
            const string query = "select * from companies";

            var command = new MySqlCommand(query, Connection);

            using (var reader = await command.ExecuteReaderAsync())
            {
                while (await reader.ReadAsync())
                    retList.Add(new Company(reader["full_name"].ToString(), reader["short_name"].ToString()));
            }

            return retList;
        }
    }
}