using System.Collections.Generic;
using System.Linq;
using NewMvcProject.Models;

namespace IIS
{
    public class CartManager
    {
        public Dictionary<string, Cart> Carts { get; } = new Dictionary<string, Cart>();

        public int GetItemCount(ApplicationUser user)
        {
            return Carts.ContainsKey(user.Email) ? Carts[user.Email].TicketIds.Count : 0;
        }

        public List<long> GetItems(ApplicationUser user)
        {
            return Carts.ContainsKey(user.Email) ?
                Carts[user.Email].TicketIds :
                new List<long>();
        }

        public void AddItems(ApplicationUser user, IEnumerable<long> ids)
        {
            if (!Carts.ContainsKey(user.Email))
                Carts.Add(user.Email, new Cart());

            foreach (var id in ids)
            {
                if (!Carts[user.Email].TicketIds.Contains(id))
                    Carts[user.Email].TicketIds.Add(id);
            }
        }

        public void RemoveItems(ApplicationUser user, IEnumerable<long> ids)
        {
            Carts[user.Email].TicketIds.RemoveAll(ids.Contains);
        }
    }
}