using System;
using System.Threading.Tasks;
using IIS.Models.Tickets;
using MySql.Data.MySqlClient;

namespace IIS.Queries
{
    public static class EmployeesQueries
    {
        private static readonly MySqlConnection Connection = (MySqlConnection)Program.Connection.Clone();

        static EmployeesQueries()
        {
            Connection.Open();
        }

        public static async Task<Company> GetByEmail(string email)
        {
            var query = $"select * from employees where email='{DbUtils.EscapeString(email)}'";

            var command = new MySqlCommand(query, Connection);

            using (var reader = await command.ExecuteReaderAsync())
            {
                await reader.ReadAsync();
                return await CompanyQueries.GetByFull(reader["company_name"].ToString());

            }
        }
    }
}