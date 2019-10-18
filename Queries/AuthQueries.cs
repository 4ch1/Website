using System;
using System.Collections.Generic;
using System.Data.Common;
using System.Threading.Tasks;
using IIS.Models.Exception;
using Microsoft.AspNetCore.Mvc;
using MySql.Data.MySqlClient;
using NewMvcProject.Models;

namespace IIS.Queries
{
    public static class AuthQueries
    {
        private static readonly MySqlConnection Connection = (MySqlConnection)Program.Connection.Clone();

        static AuthQueries()
        {
            Connection.Open();
        }

        public static async Task<ApplicationUser> GetByEmail(string email)
        {
            var query = $"select * from clients where email = '{email}'";

            var command = new MySqlCommand(query, Connection);

            using (var reader = await command.ExecuteReaderAsync())
            {
                if (!reader.HasRows)
                    return null;

                await reader.ReadAsync();
                return BuildUser(reader);
            }
        }

        private static ApplicationUser BuildUser(DbDataReader reader)
        {
            return new ApplicationUser(Convert.ToString(reader["email"]),
                Convert.ToString(reader["password"]),
                Convert.ToString(reader["first_name"]), Convert.ToString(reader["last_name"]),
                Convert.ToString(reader["address"]), (ApplicationUser.RightsEnum)Convert.ToInt16(reader["access_level"]));
        }

        public static async Task CreateUserAsync(ApplicationUser user)
        {
            var query =
                $"insert into clients values ('{DbUtils.EscapeString(user.Email)}','{DbUtils.EscapeString(user.Password)}','{DbUtils.EscapeString(user.FirstName)}','{DbUtils.EscapeString(user.LastName)}','{DbUtils.EscapeString(user.Address)}',{(int)user.Rights})";

            var command = new MySqlCommand(query, Connection);

            await command.ExecuteNonQueryAsync();
        }

        public static async Task<List<string>> GetAllEmails()
        {
            List<string> retList = new List<string>();
            var query = $"select email from clients";

            var command = new MySqlCommand(query, Connection);

            using (var reader = await command.ExecuteReaderAsync())
            {
                while (await reader.ReadAsync())
                    retList.Add(Convert.ToString(reader["email"]));
            }

            return retList;
        }
    }
}