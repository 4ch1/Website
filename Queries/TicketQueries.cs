using System;
using System.Collections.Generic;
using System.Data.Common;
using System.Threading.Tasks;
using IIS.Models.Tickets;
using MySql.Data.MySqlClient;

namespace IIS.Queries
{
    public static class TicketQueries
    {
        private static readonly MySqlConnection Connection = Program.Connection;

        public static async Task<List<Ticket>> GetAllTickets(string fromAirport, string toAirport, string date)
        {
            var retList = new List<Ticket>();
            var query =
                $"select * from tickets where from_airport_short in (select short_name from airports where location = '{fromAirport}') and to_airport_short in (select short_name from airports where location = '{toAirport}') and date like '{date}%'";

            var command = new MySqlCommand(query, Connection);

            using (var reader = await command.ExecuteReaderAsync())
            {
                while (await reader.ReadAsync())
                    retList.Add(await BuildTicket(reader));
            }

            return retList;
        }

        private static async Task<Ticket> BuildTicket(DbDataReader reader)
        {
            return new Ticket(Convert.ToInt64(reader["id"]),
                await AirportQueries.GetByShort(Convert.ToString(reader["from_airport_short"])),
                await AirportQueries.GetByShort(Convert.ToString(reader["to_airport_short"])),
                DateTime.Parse(reader["date"].ToString()),
                Convert.ToDecimal(reader["price"]),
                await CompanyQueries.GetByFull(reader["company"].ToString()),
                BuildCategory(reader["category"].ToString()));
        }

        private static Category BuildCategory(string categoryName)
        {
            return categoryName.Equals("Business class")
                ? new Category(CategoryEnum.BUSINESS)
                : new Category(CategoryEnum.ECONOMY);
        }

        public static async Task<IEnumerable<Ticket>> GetAllTickets(List<long> ids)
        {
            if (ids.Count == 0)
                return new List<Ticket>();

            var retList = new List<Ticket>();
            var query = ids.Count > 1 ?
                $"select * from tickets where id in ({string.Join(",", ids)})"
                : $"select * from tickets where id = {ids[0]}";

            var command = new MySqlCommand(query, Connection);

            using (var reader = await command.ExecuteReaderAsync())
            {
                while (await reader.ReadAsync())
                    retList.Add(await BuildTicket(reader));
            }

            return retList;
        }

        public static async Task<IEnumerable<Ticket>> GetAllTickets(string companyName)
        {
            var retList = new List<Ticket>();
            var query = $"select * from tickets where company = '{companyName}'";

            var command = new MySqlCommand(query, Connection);

            using (var reader = await command.ExecuteReaderAsync())
            {
                while (await reader.ReadAsync())
                    retList.Add(await BuildTicket(reader));
            }

            return retList;
        }

        public static async Task Add(string date, string toAirport, string fromAirport, string time, string category, string fullName, string price)
        {
            var query = $"insert into tickets values (null,'{fromAirport}','{toAirport}','{date} {time}',{price},'{fullName}','{category}')";

            var command = new MySqlCommand(query, Connection);

            await command.ExecuteNonQueryAsync();
        }

        public static async Task<Ticket> GetTicket(long ticketId)
        {
            var query = $"select * from tickets where id = {ticketId}";

            var command = new MySqlCommand(query, Connection);

            using (var reader = await command.ExecuteReaderAsync())
            {
                if (!reader.HasRows)
                    return null;

                await reader.ReadAsync();
                return await BuildTicket(reader);
            }
        }

        public static async Task Delete(string id)
        {
            var query = $"delete from tickets where id = {id}";

            var command = new MySqlCommand(query, Connection);

            await command.ExecuteNonQueryAsync();
        }

        public static async Task Update(string id, string date, string category, string price)
        {
            var query = $"update tickets set date='{date}',category='{category}',price='{price}' where id = {id}";

            var command = new MySqlCommand(query, Connection);

            await command.ExecuteNonQueryAsync();
        }
    }
}