using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using IIS.Models.Tickets;
using MySql.Data.MySqlClient;

namespace IIS.Queries
{
    public static class AirportQueries
    {
        private static readonly MySqlConnection Connection = (MySqlConnection)Program.Connection.Clone();

        static AirportQueries()
        {
            Connection.Open();
        }

        public static async Task<IEnumerable<Airport>> GetAllAirports()
        {
            var retList = new List<Airport>();
            var query = $"select * from airports";

            var command = new MySqlCommand(query, Connection);

            using (var reader = await command.ExecuteReaderAsync())
            {
                while (await reader.ReadAsync())
                    retList.Add(new Airport(
                        Convert.ToString(reader["full_name"]),
                        Convert.ToString(reader["short_name"]),
                        Convert.ToString(reader["location"])));
            }

            return retList;
        }

        internal static async Task<List<string>> GetAllAirports(string startMatch)
        {
            var retList = new List<string>();
            var query = $"select location from airports where location like '{DbUtils.EscapeString(startMatch)}%'";

            var command = new MySqlCommand(query, Connection);

            using (var reader = await command.ExecuteReaderAsync())
            {
                while (await reader.ReadAsync())
                    retList.Add(Convert.ToString(reader["location"]));
            }

            return retList;
        }

        public static async Task<Airport> GetByShort(string shortString)
        {
            var query = $"select * from airports where short_name = '{shortString}'";

            var command = new MySqlCommand(query, Connection);

            using (var reader = await command.ExecuteReaderAsync())
            {
                await reader.ReadAsync();
                return new Airport(
                Convert.ToString(reader["full_name"]),
                Convert.ToString(reader["short_name"]),
                Convert.ToString(reader["location"]));

            }
        }

        public static async Task<List<string>> GetAllAirportsShort(string term)
        {
            var retList = new List<string>();
            var query = $"select short_name from airports where short_name like '{DbUtils.EscapeString(term)}%'";

            var command = new MySqlCommand(query, Connection);

            using (var reader = await command.ExecuteReaderAsync())
            {
                while (await reader.ReadAsync())
                    retList.Add(Convert.ToString(reader["short_name"]));
            }

            return retList;
        }
    }
}